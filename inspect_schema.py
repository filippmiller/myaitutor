from sqlalchemy import text
from app.database import engine
from sqlmodel import Session

def inspect_schema():
    with Session(engine) as session:
        print("Inspecting userprofile columns:")
        result = session.exec(text("SELECT column_name, data_type, is_nullable, column_default FROM information_schema.columns WHERE table_name = 'userprofile';")).all()
        for row in result:
            print(row)

if __name__ == "__main__":
    inspect_schema()
