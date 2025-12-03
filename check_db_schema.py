from sqlmodel import Session, text
from app.database import engine
from sqlalchemy import inspect

def check_schema():
    print("Checking database schema...")
    inspector = inspect(engine)
    columns = [c['name'] for c in inspector.get_columns('userprofile')]
    print(f"Columns in userprofile: {columns}")
    
    expected = ['preferred_tts_engine', 'preferred_stt_engine', 'preferred_voice_id']
    for col in expected:
        if col in columns:
            print(f"✅ {col} exists")
        else:
            print(f"❌ {col} MISSING")

if __name__ == "__main__":
    check_schema()
