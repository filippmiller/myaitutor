from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from sqlmodel import Session, select
from app.models import UserAccount, UserProfile, WalletTransaction, BillingPackage

class BillingService:
    def __init__(self, session: Session):
        self.session = session

    def get_user_balance(self, user_id: int) -> int:
        """
        Calculate user balance by summing up all transaction minutes_delta.
        Also updates the cache field in UserProfile.
        """
        statement = select(WalletTransaction).where(WalletTransaction.user_account_id == user_id)
        transactions = self.session.exec(statement).all()
        balance = sum(t.minutes_delta for t in transactions)
        
        # Update cache
        self._update_balance_cache(user_id, balance)
        return balance

    def _update_balance_cache(self, user_id: int, balance: int):
        profile = self.session.exec(select(UserProfile).where(UserProfile.user_account_id == user_id)).first()
        if profile:
            profile.minutes_balance = balance
            self.session.add(profile)
            self.session.commit()
            self.session.refresh(profile)

    def create_trial_bonus(self, user_id: int) -> WalletTransaction:
        """
        Award 60 free minutes to a new user.
        Should be called only once per user (check logic in caller or here).
        """
        # Check if trial already exists
        existing = self.session.exec(
            select(WalletTransaction)
            .where(WalletTransaction.user_account_id == user_id)
            .where(WalletTransaction.type == "trial")
        ).first()
        
        if existing:
            return existing

        tx = WalletTransaction(
            user_account_id=user_id,
            type="trial",
            minutes_delta=60,
            reason="Free trial signup",
            source="system"
        )
        self.session.add(tx)
        self.session.commit()
        self.session.refresh(tx)
        
        self.get_user_balance(user_id) # Recalculate and cache
        return tx

    def process_deposit(self, user_id: int, amount_rub: Decimal) -> WalletTransaction:
        """
        Process a deposit: find applicable package, calculate minutes with discount.
        """
        # Find best package: max min_amount_rub that is <= amount_rub
        # We assume packages are sorted by min_amount_rub desc or we sort here
        packages = self.session.exec(
            select(BillingPackage)
            .where(BillingPackage.is_active == True)
            .order_by(BillingPackage.min_amount_rub.desc())
        ).all()

        selected_package = None
        for pkg in packages:
            if amount_rub >= pkg.min_amount_rub:
                selected_package = pkg
                break
        
        discount_percent = selected_package.discount_percent if selected_package else 0
        base_rate = Decimal("5.00") # 5 RUB per minute
        
        # Effective rate = 5 * (1 - discount/100)
        effective_rate = base_rate * (1 - Decimal(discount_percent) / 100)
        
        # Minutes = amount / effective_rate
        # Example: 1000 RUB, 10% discount. Rate = 5 * 0.9 = 4.5. Minutes = 1000 / 4.5 = 222.22 -> 222
        minutes = int(amount_rub / effective_rate)
        
        tx = WalletTransaction(
            user_account_id=user_id,
            type="deposit",
            amount_rub=amount_rub,
            minutes_delta=minutes,
            source="deposit_package",
            source_ref=str(selected_package.id) if selected_package else None,
            reason=f"Deposit {amount_rub} RUB (Package: {selected_package.description if selected_package else 'None'})"
        )
        self.session.add(tx)
        self.session.commit()
        self.session.refresh(tx)
        
        self.get_user_balance(user_id)
        return tx

    def gift_minutes(self, user_id: int, minutes: int, reason: str, admin_id: Optional[int] = None) -> WalletTransaction:
        tx = WalletTransaction(
            user_account_id=user_id,
            type="gift",
            minutes_delta=minutes,
            reason=reason,
            source="admin",
            source_ref=str(admin_id) if admin_id else None
        )
        self.session.add(tx)
        self.session.commit()
        self.session.refresh(tx)
        
        self.get_user_balance(user_id)
        return tx
