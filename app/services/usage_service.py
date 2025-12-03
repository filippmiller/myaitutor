from datetime import datetime
from decimal import Decimal
from typing import Optional
from sqlmodel import Session, select
from app.models import UsageSession, WalletTransaction, BillingPackage

class UsageService:
    def __init__(self, session: Session):
        self.session = session

    def record_session(self, user_id: int, started_at: datetime, ended_at: datetime) -> UsageSession:
        """
        Record a voice session and charge the user.
        """
        duration_sec = int((ended_at - started_at).total_seconds())
        
        # Calculate billed minutes (round up?)
        # For now, let's say we round up to the next minute
        billed_minutes = (duration_sec + 59) // 60
        if billed_minutes < 1:
            billed_minutes = 1 # Minimum 1 minute if session happened? Or 0 if very short?
            # Let's assume minimum 1 minute for simplicity if duration > 0
        
        if duration_sec == 0:
            billed_minutes = 0

        # Calculate cost for analytics (base rate 5 RUB)
        base_rate = Decimal("5.00")
        billed_amount_rub = Decimal(billed_minutes) * base_rate

        # Capture tariff snapshot
        import json
        tariff_snapshot = {
            "base_rate_rub_per_min": 5,
            "currency": "RUB",
            "timestamp": datetime.utcnow().isoformat()
        }

        usage = UsageSession(
            user_account_id=user_id,
            started_at=started_at,
            ended_at=ended_at,
            duration_sec=duration_sec,
            billed_minutes=billed_minutes,
            billed_amount_rub=billed_amount_rub,
            billing_status="pending",
            tariff_snapshot=json.dumps(tariff_snapshot)
        )
        self.session.add(usage)
        self.session.commit()
        self.session.refresh(usage)

        # Charge the user
        self._charge_user(usage)
        
        return usage

    def _charge_user(self, usage: UsageSession):
        if usage.billed_minutes > 0:
            tx = WalletTransaction(
                user_account_id=usage.user_account_id,
                type="usage",
                minutes_delta=-usage.billed_minutes,
                source="session",
                source_ref=str(usage.id),
                reason=f"Voice session {usage.duration_sec}s"
            )
            self.session.add(tx)
            
            usage.billing_status = "billed"
            self.session.add(usage)
            
            self.session.commit()
            
            # Update balance cache (could inject BillingService or duplicate logic)
            # For simplicity, let's duplicate the cache update logic or import it if needed.
            # Better: use a shared helper or just let the next read update it? 
            # Let's do a quick update here.
            from app.models import UserProfile
            profile = self.session.exec(select(UserProfile).where(UserProfile.user_account_id == usage.user_account_id)).first()
            if profile:
                # We can just decrement the cache for speed, or recalculate.
                # Recalculating is safer.
                # But we don't have BillingService here. 
                # Let's just decrement for now, assuming it was correct.
                profile.minutes_balance -= usage.billed_minutes
                self.session.add(profile)
                self.session.commit()
        else:
            usage.billing_status = "free"
            self.session.add(usage)
            self.session.commit()
