import sys
import os
from datetime import datetime, timedelta
from decimal import Decimal
from sqlmodel import Session, select, delete
from app.database import engine
from app.models import UserAccount, UserProfile, WalletTransaction, UsageSession, Referral, BillingPackage
from app.services.billing_service import BillingService
from app.services.usage_service import UsageService
from app.services.referral_service import ReferralService

def run_verification():
    print("Starting Phase 2 Verification...")
    
    with Session(engine) as session:
        # Cleanup test data
        print("Cleaning up old test data...")
        test_email_1 = "test_user_a@example.com"
        test_email_2 = "test_user_b@example.com"
        
        for email in [test_email_1, test_email_2]:
            user = session.exec(select(UserAccount).where(UserAccount.email == email)).first()
            if user:
                # Delete related data
                session.exec(delete(WalletTransaction).where(WalletTransaction.user_account_id == user.id))
                session.exec(delete(UsageSession).where(UsageSession.user_account_id == user.id))
                session.exec(delete(Referral).where(Referral.referrer_user_id == user.id))
                session.exec(delete(Referral).where(Referral.referred_user_id == user.id))
                session.exec(delete(UserProfile).where(UserProfile.user_account_id == user.id))
                session.delete(user)
        session.commit()

        # Initialize Services
        billing_service = BillingService(session)
        usage_service = UsageService(session)
        referral_service = ReferralService(session)

        # Scenario 1: Registration (Trial)
        print("\n--- Scenario 1: Registration (Trial) ---")
        user_a = UserAccount(email=test_email_1, hashed_password="hash", is_active=True)
        session.add(user_a)
        session.commit()
        session.refresh(user_a)
        
        profile_a = UserProfile(user_account_id=user_a.id, name="User A", english_level="B1")
        session.add(profile_a)
        session.commit()
        
        # Award trial
        billing_service.create_trial_bonus(user_a.id)
        
        # Verify
        balance_a = billing_service.get_user_balance(user_a.id)
        print(f"User A Balance: {balance_a} (Expected: 60)")
        if balance_a != 60:
            print("FAIL: Trial bonus not applied correctly")
            sys.exit(1)
            
        # Scenario 2: Deposit
        print("\n--- Scenario 2: Deposit ---")
        # Ensure package exists
        pkg = session.exec(select(BillingPackage).where(BillingPackage.min_amount_rub == 1000)).first()
        if not pkg:
            pkg = BillingPackage(min_amount_rub=1000, discount_percent=10, description="Standard")
            session.add(pkg)
            session.commit()
            
        # Deposit 1000 RUB
        # Rate = 5 * 0.9 = 4.5. Minutes = 1000 / 4.5 = 222
        billing_service.process_deposit(user_a.id, Decimal("1000"))
        
        balance_a = billing_service.get_user_balance(user_a.id)
        print(f"User A Balance after deposit: {balance_a} (Expected: 60 + 222 = 282)")
        if balance_a != 282:
            print("FAIL: Deposit calculation incorrect")
            sys.exit(1)

        # Scenario 3: Usage
        print("\n--- Scenario 3: Usage ---")
        start_time = datetime.utcnow()
        end_time = start_time + timedelta(minutes=7, seconds=15) # 7m 15s -> 8 minutes
        
        usage_service.record_session(user_a.id, start_time, end_time)
        
        balance_a = billing_service.get_user_balance(user_a.id)
        print(f"User A Balance after usage: {balance_a} (Expected: 282 - 8 = 274)")
        if balance_a != 274:
            print("FAIL: Usage deduction incorrect")
            sys.exit(1)
            
        # Check tariff snapshot
        usage_rec = session.exec(select(UsageSession).where(UsageSession.user_account_id == user_a.id)).first()
        if not usage_rec.tariff_snapshot:
             print("FAIL: Tariff snapshot missing")
             sys.exit(1)
        print(f"Tariff Snapshot: {usage_rec.tariff_snapshot}")

        # Scenario 4: Gift
        print("\n--- Scenario 4: Admin Gift ---")
        billing_service.gift_minutes(user_a.id, 10, "Test Gift")
        balance_a = billing_service.get_user_balance(user_a.id)
        print(f"User A Balance after gift: {balance_a} (Expected: 274 + 10 = 284)")
        if balance_a != 284:
            print("FAIL: Gift not applied")
            sys.exit(1)

        # Scenario 5: Referral
        print("\n--- Scenario 5: Referral ---")
        # User B registers with User A's code
        ref_code = referral_service.generate_referral_code(user_a.id)
        print(f"User A Referral Code: {ref_code}")
        
        user_b = UserAccount(email=test_email_2, hashed_password="hash", is_active=True)
        session.add(user_b)
        session.commit()
        session.refresh(user_b)
        profile_b = UserProfile(user_account_id=user_b.id, name="User B", english_level="A1")
        session.add(profile_b)
        session.commit()
        
        # B gets trial
        billing_service.create_trial_bonus(user_b.id)
        
        # Process referral
        referral_service.process_referral_signup(user_b.id, ref_code)
        
        # Verify rewards
        balance_a = billing_service.get_user_balance(user_a.id)
        balance_b = billing_service.get_user_balance(user_b.id)
        
        print(f"User A Balance (Referrer): {balance_a} (Expected: 284 + 60 = 344)")
        print(f"User B Balance (Referred): {balance_b} (Expected: 60 + 60 = 120)")
        
        if balance_a != 344 or balance_b != 120:
             print("FAIL: Referral rewards incorrect")
             sys.exit(1)

    print("\nSUCCESS: All Phase 2 scenarios verified!")

if __name__ == "__main__":
    run_verification()
