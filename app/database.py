from sqlmodel import SQLModel, create_engine, Session

import os
from dotenv import load_dotenv

load_dotenv()

sqlite_file_name = "database.db"
sqlite_url = f"sqlite:///{sqlite_file_name}"
# Default to SQLite if DATABASE_URL is not set (fallback)
database_url = os.getenv("DATABASE_URL", sqlite_url)

# Fix for SQLAlchemy/Postgres
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

# PostgreSQL does not need check_same_thread
connect_args = {"check_same_thread": False} if "sqlite" in database_url else {}
engine = create_engine(database_url, echo=False, connect_args=connect_args)

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as session:
        yield session
