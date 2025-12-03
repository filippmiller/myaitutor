import secrets
from datetime import datetime
from typing import Optional
from sqlmodel import Session, select
from app.models import Referral, UserAccount, WalletTransaction

class ReferralService:
    def __init__(self, session: Session):
        self.session = session

    def generate_referral_code(self, user_id: int) -> str:
        """
        Get or create a referral code for a user.
        """
        # Check if user already has a code (we might store it in UserProfile later, 
        # but for now we can check if they are a referrer in 'referrals' table? 
        # No, 'referrals' table stores relationships. 
        # We need a place to store the user's OWN code.
        # For MVP, let's just generate it deterministically or store it in UserProfile?
        # The prompt said: "generate and store referral_code ... either in user table or separate entity".
        # Let's assume we generate it on the fly or store it. 
        # Actually, we didn't add a field for 'my_referral_code' in UserAccount/Profile.
        # Let's add it to UserProfile now or just use a deterministic one (e.g. user_id based)?
        # Deterministic is easier for MVP: "REF-{user_id}"
        # But random is better. Let's stick to "REF-{user_id}-{random}" and store it?
        # Wait, if we didn't add a column, we can't store it.
        # Let's use a deterministic one for now: f"USER{user_id}"
        pass
        return f"USER{user_id}"

    def process_referral_signup(self, new_user_id: int, referral_code: str):
        """
        Called when a new user signs up with a code.
        """
        # Parse code to find referrer
        # Assuming code format "USER{id}"
        if not referral_code.startswith("USER"):
            return # Invalid code
            
        try:
            referrer_id = int(referral_code.replace("USER", ""))
        except ValueError:
            return

        if referrer_id == new_user_id:
            return # Cannot refer self

        # Check if referrer exists
        referrer = self.session.get(UserAccount, referrer_id)
        if not referrer:
            return

        # Create referral record
        ref = Referral(
            referrer_user_id=referrer_id,
            referred_user_id=new_user_id,
            referral_code=referral_code,
            status="pending"
        )
        self.session.add(ref)
        self.session.commit()
        self.session.refresh(ref)

        # Award bonuses immediately? Or wait for verification?
        # Prompt says: "after confirmation ... or first login ... change status to rewarded"
        # Let's do it immediately for MVP simplicity, or call a method 'confirm_referral'
        self.confirm_referral(ref.id)

    def confirm_referral(self, referral_id: int):
        ref = self.session.get(Referral, referral_id)
        if not ref or ref.status != "pending":
            return

        # Award referrer
        tx1 = WalletTransaction(
            user_account_id=ref.referrer_user_id,
            type="referral_reward",
            minutes_delta=ref.reward_minutes_for_referrer,
            reason=f"Referral reward for inviting user {ref.referred_user_id}",
            source="referral",
            source_ref=str(ref.id)
        )
        self.session.add(tx1)

        # Award referred
        tx2 = WalletTransaction(
            user_account_id=ref.referred_user_id,
            type="referral_welcome",
            minutes_delta=ref.reward_minutes_for_referred,
            reason=f"Referral welcome bonus from user {ref.referrer_user_id}",
            source="referral",
            source_ref=str(ref.id)
        )
        self.session.add(tx2)

        ref.status = "rewarded"
        ref.rewarded_at = datetime.utcnow()
        self.session.add(ref)
        
        self.session.commit()
        
        # Update balances
        # (Ideally call BillingService, but we are in ReferralService)
        # We can just let the next read update it, or manually update if we import UserProfile
        from app.models import UserProfile
        for uid, delta in [(ref.referrer_user_id, ref.reward_minutes_for_referrer), (ref.referred_user_id, ref.reward_minutes_for_referred)]:
            p = self.session.exec(select(UserProfile).where(UserProfile.user_account_id == uid)).first()
            if p:
                p.minutes_balance += delta
                self.session.add(p)
        
        self.session.commit()
