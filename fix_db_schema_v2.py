import os
from sqlalchemy import text
from app.database import engine
from sqlmodel import Session

def fix_schema():
    print("Starting Schema Fix...")
    
    # Verify DB Connection
    db_url = os.getenv("DATABASE_URL", "")
    print(f"Connected to: {db_url.split('@')[-1] if '@' in db_url else 'UNKNOWN'}")

    with Session(engine) as session:
        # 1. Fix minutes_balance
        print("\nChecking minutes_balance...")
        try:
            # Check if exists
            result = session.exec(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'userprofile' AND column_name = 'minutes_balance';")).first()
            if not result:
                print("Column missing. Adding...")
                session.exec(text("ALTER TABLE userprofile ADD COLUMN minutes_balance INTEGER NOT NULL DEFAULT 0;"))
                session.commit()
                print("Added minutes_balance.")
            else:
                print("minutes_balance already exists.")
        except Exception as e:
            print(f"Error checking/adding minutes_balance: {e}")
            session.rollback()

        # 2. Fix tariff_snapshot type
        print("\nChecking tariff_snapshot type...")
        try:
            # Check data type
            result = session.exec(text("SELECT data_type FROM information_schema.columns WHERE table_name = 'usage_sessions' AND column_name = 'tariff_snapshot';")).first()
            if result:
                current_type = result[0]
                print(f"Current type: {current_type}")
                if current_type not in ('json', 'jsonb'):
                    print("Converting to JSONB...")
                    # We need to cast existing data. If it's NULL, it's easy. If it's string JSON, we cast.
                    session.exec(text("ALTER TABLE usage_sessions ALTER COLUMN tariff_snapshot TYPE JSONB USING tariff_snapshot::jsonb;"))
                    session.commit()
                    print("Converted tariff_snapshot to JSONB.")
                else:
                    print("tariff_snapshot is already JSON/JSONB.")
            else:
                print("tariff_snapshot column not found (unexpected).")
        except Exception as e:
            print(f"Error converting tariff_snapshot: {e}")
            session.rollback()

if __name__ == "__main__":
    fix_schema()
