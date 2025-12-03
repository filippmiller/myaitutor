from sqlmodel import Session, select
from app.database import engine
from app.models import UserProfile, UserAccount

def check_user_1():
    print("Checking User 1...")
    with Session(engine) as session:
        user = session.get(UserAccount, 1)
        print(f"User: {user}")
        
        profile = session.exec(select(UserProfile).where(UserProfile.user_account_id == 1)).first()
        print(f"Profile: {profile}")
        if profile:
            print(f"Preferences (raw): {profile.preferences}")
            print(f"Type of preferences: {type(profile.preferences)}")

if __name__ == "__main__":
    check_user_1()
