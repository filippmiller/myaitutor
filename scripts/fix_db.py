from sqlmodel import Session, create_engine, text
from app.database import engine
from app.models import AppSettings

def fix_and_update():
    with Session(engine) as session:
        # 1. Fix Schema (Add missing columns)
        print("Checking/Fixing schema...")
        try:
            session.exec(text("ALTER TABLE appsettings ADD COLUMN deepgram_api_key VARCHAR"))
            print("Added deepgram_api_key column")
        except Exception as e:
            print(f"Column deepgram_api_key might already exist: {e}")
            session.rollback()

        try:
            session.exec(text("ALTER TABLE appsettings ADD COLUMN deepgram_voice_id VARCHAR"))
            print("Added deepgram_voice_id column")
        except Exception as e:
            print(f"Column deepgram_voice_id might already exist: {e}")
            session.rollback()

        session.commit()

        # 2. Update Settings
        print("Updating settings...")
        settings = session.get(AppSettings, 1)
        if not settings:
            settings = AppSettings(id=1)
        
        settings.openai_api_key = "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"
        settings.default_model = "gpt-4o-mini"
        settings.deepgram_api_key = "994953cb0814cdbd98f3d95f4b152ca0c905861e"
        settings.deepgram_voice_id = "aura-asteria-en"

        session.add(settings)
        session.commit()
        print("Settings updated successfully!")

if __name__ == "__main__":
    fix_and_update()
