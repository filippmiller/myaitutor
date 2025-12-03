from sqlmodel import select, Session
from app.database import engine
from app.models import BillingPackage, WalletTransaction, UsageSession, Referral, UserProfile

def verify():
    print(f"Connecting to: {engine.url}")
    print("Verifying database schema...")
    try:
        with Session(engine) as session:
            # Check tables exist by querying them
            packages = session.exec(select(BillingPackage)).all()
            print(f"BillingPackage table exists. Count: {len(packages)}")
            
            txs = session.exec(select(WalletTransaction)).all()
            print(f"WalletTransaction table exists. Count: {len(txs)}")
            
            sessions = session.exec(select(UsageSession)).all()
            print(f"UsageSession table exists. Count: {len(sessions)}")
            
            refs = session.exec(select(Referral)).all()
            print(f"Referral table exists. Count: {len(refs)}")
            
            # Check column exists
            # We can't easily check column existence via SQLModel without inspecting, 
            # but if we query UserProfile and access minutes_balance, it should work if mapped correctly.
            # However, if the column is missing in DB, it will fail on select if we select all columns.
            profiles = session.exec(select(UserProfile).limit(1)).all()
            if profiles:
                print(f"UserProfile minutes_balance: {profiles[0].minutes_balance}")
            else:
                print("No profiles found, but table query worked.")
                
        print("Verification SUCCESS")
    except Exception as e:
        print(f"Verification FAILED: {e}")

if __name__ == "__main__":
    verify()
