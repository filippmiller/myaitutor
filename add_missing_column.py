from sqlalchemy import text
from app.database import engine
from sqlmodel import Session

def add_column():
    print("Adding minutes_balance column...")
    with Session(engine) as session:
        try:
            session.exec(text("ALTER TABLE userprofile ADD COLUMN IF NOT EXISTS minutes_balance INTEGER NOT NULL DEFAULT 0;"))
            session.commit()
            print("Success: Column added.")
        except Exception as e:
            print(f"Error: {e}")
            session.rollback()

if __name__ == "__main__":
    add_column()
