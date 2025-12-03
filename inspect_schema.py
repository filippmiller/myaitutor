from sqlalchemy import text
from app.database import engine
from sqlmodel import Session

def inspect_schema():
    tables = ['billing_packages', 'wallet_transactions']
    with Session(engine) as session:
        for table in tables:
            print(f"\n=== Inspecting {table} ===")
            try:
                result = session.exec(text(f"SELECT column_name, data_type, is_nullable, column_default FROM information_schema.columns WHERE table_name = '{table}';")).all()
                if not result:
                    print(f"Table {table} NOT FOUND or empty schema info.")
                for row in result:
                    print(row)
            except Exception as e:
                print(f"Error inspecting {table}: {e}")

if __name__ == "__main__":
    inspect_schema()
