import os
from sqlmodel import create_engine, Session, SQLModel, select, text
from app.models import TutorSystemRule, UserAccount
from app.database import engine

def update_schema():
    print(f"Connecting to database...")
    
    with Session(engine) as session:
        # 1. Add role to user_accounts
        try:
            session.exec(text("ALTER TABLE user_accounts ADD COLUMN role VARCHAR DEFAULT 'student'"))
            session.commit()
            print("Added role column to user_accounts")
        except Exception as e:
            print(f"Note: role column update skipped (probably exists): {e}")
            session.rollback()

        # 2. Add preferences to userprofile
        try:
            session.exec(text("ALTER TABLE userprofile ADD COLUMN preferences VARCHAR DEFAULT '{}'"))
            session.commit()
            print("Added preferences column to userprofile")
        except Exception as e:
            print(f"Note: preferences column update skipped (probably exists): {e}")
            session.rollback()

    # 3. Create TutorSystemRule table
    # SQLModel.metadata.create_all(engine) checks existence but sometimes it's tricky with updates.
    # But since TutorSystemRule is new, create_all should work fine.
    SQLModel.metadata.create_all(engine)
    print("Created new tables (if any)")

    # 4. Seed Rules
    with Session(engine) as session:
        # Check if rules exist
        try:
            if not session.exec(select(TutorSystemRule)).first():
                rules = [
                    TutorSystemRule(
                        rule_key="greeting.addressing",
                        rule_text="If the student has a preferred form of address, use it. If not, politely ask how they would like to be addressed.",
                        sort_order=10,
                        enabled=True
                    ),
                    TutorSystemRule(
                        rule_key="greeting.last_lesson",
                        rule_text="Briefly mention the topic of the last lesson if available to provide continuity.",
                        sort_order=20,
                        enabled=True
                    ),
                    TutorSystemRule(
                        rule_key="adaptation.level",
                        rule_text="Strictly adapt your vocabulary and grammar to the student's level. Use simple sentences for A1-A2.",
                        sort_order=30,
                        enabled=True
                    )
                ]
                session.add_all(rules)
                session.commit()
                print("Seeded system rules")
            else:
                print("System rules already seeded")
        except Exception as e:
            print(f"Error seeding rules: {e}")

if __name__ == "__main__":
    update_schema()
