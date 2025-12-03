from sqlalchemy import text
from app.database import engine
from sqlmodel import Session

def run_manual_migration():
    print(f"Connecting to DB: {engine.url}")
    
    statements = [
        """
        CREATE TABLE IF NOT EXISTS billing_packages (
            id SERIAL NOT NULL,
            min_amount_rub NUMERIC(10, 2),
            discount_percent INTEGER NOT NULL,
            description VARCHAR,
            is_active BOOLEAN NOT NULL,
            sort_order INTEGER NOT NULL,
            created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
            updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
            PRIMARY KEY (id)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS referrals (
            id SERIAL NOT NULL,
            referrer_user_id INTEGER NOT NULL,
            referred_user_id INTEGER NOT NULL,
            referral_code VARCHAR NOT NULL,
            status VARCHAR NOT NULL,
            reward_minutes_for_referrer INTEGER NOT NULL,
            reward_minutes_for_referred INTEGER NOT NULL,
            created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
            rewarded_at TIMESTAMP WITHOUT TIME ZONE,
            PRIMARY KEY (id),
            FOREIGN KEY(referred_user_id) REFERENCES user_accounts (id),
            FOREIGN KEY(referrer_user_id) REFERENCES user_accounts (id)
        );
        """,
        "CREATE INDEX IF NOT EXISTS ix_referrals_referral_code ON referrals (referral_code);",
        "CREATE INDEX IF NOT EXISTS ix_referrals_referred_user_id ON referrals (referred_user_id);",
        "CREATE INDEX IF NOT EXISTS ix_referrals_referrer_user_id ON referrals (referrer_user_id);",
        """
        CREATE TABLE IF NOT EXISTS usage_sessions (
            id SERIAL NOT NULL,
            user_account_id INTEGER NOT NULL,
            started_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
            ended_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
            duration_sec INTEGER NOT NULL,
            billed_minutes INTEGER NOT NULL,
            billed_amount_rub NUMERIC(10, 2),
            billing_status VARCHAR NOT NULL,
            tariff_snapshot VARCHAR,
            created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
            PRIMARY KEY (id),
            FOREIGN KEY(user_account_id) REFERENCES user_accounts (id)
        );
        """,
        "CREATE INDEX IF NOT EXISTS ix_usage_sessions_user_account_id ON usage_sessions (user_account_id);",
        """
        CREATE TABLE IF NOT EXISTS wallet_transactions (
            id SERIAL NOT NULL,
            user_account_id INTEGER NOT NULL,
            type VARCHAR NOT NULL,
            amount_rub NUMERIC(10, 2),
            minutes_delta INTEGER NOT NULL,
            source VARCHAR,
            source_ref VARCHAR,
            reason VARCHAR,
            created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
            PRIMARY KEY (id),
            FOREIGN KEY(user_account_id) REFERENCES user_accounts (id)
        );
        """,
        "CREATE INDEX IF NOT EXISTS ix_wallet_transactions_user_account_id ON wallet_transactions (user_account_id);",
        "ALTER TABLE userprofile ADD COLUMN IF NOT EXISTS minutes_balance INTEGER NOT NULL DEFAULT 0;",
        "INSERT INTO alembic_version (version_num) VALUES ('0e7f8248675f') ON CONFLICT DO NOTHING;"
    ]

    try:
        with Session(engine) as session:
            for stmt in statements:
                print(f"Executing: {stmt[:50]}...")
                try:
                    session.exec(text(stmt))
                    session.commit()
                    print("Success.")
                except Exception as e:
                    print(f"Error executing statement: {e}")
                    session.rollback()
                    # Continue? Or stop?
                    # If table exists, it might fail if IF NOT EXISTS is not supported (Postgres supports it).
                    # But indexes might fail if they exist.
                    # Let's continue.

    except Exception as e:
        print(f"Connection failed: {e}")

if __name__ == "__main__":
    run_manual_migration()
