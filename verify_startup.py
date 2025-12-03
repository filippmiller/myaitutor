import sys
from sqlmodel import Session, select
from app.database import engine
from app.models import UserProfile

def verify_startup():
    print("Verifying App Startup & DB Connection...")
    try:
        # 1. Initialize DB (simulating startup)
        # create_db_and_tables() # We assume tables exist
        
        # 2. Try a query that touches the problematic column
        with Session(engine) as session:
            print("Querying UserProfile...")
            # Select first profile
            profile = session.exec(select(UserProfile)).first()
            if profile:
                print(f"Found profile: {profile.id}")
                print(f"Minutes Balance: {profile.minutes_balance}")
                print(f"Tariff Snapshot (UsageSession check skipped, but models loaded)")
            else:
                print("No profiles found, but query succeeded.")
                
        print("SUCCESS: App startup simulation passed.")
    except Exception as e:
        print(f"FAIL: Startup failed with error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    verify_startup()
