from sqlalchemy import text
from app.database import engine
from sqlmodel import Session

def check_columns():
    print("Checking userprofile columns...")
    with Session(engine) as session:
        result = session.exec(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'userprofile';")).all()
        columns = [row[0] for row in result]
        print(f"Columns: {columns}")
        if 'minutes_balance' in columns:
            print("minutes_balance EXISTS")
        else:
            print("minutes_balance MISSING")

if __name__ == "__main__":
    check_columns()
