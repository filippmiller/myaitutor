import json
from sqlmodel import Session, select
from app.database import engine
from app.models import UserProfile, UserAccount

def check_preferences(email):
    with Session(engine) as session:
        user = session.exec(select(UserAccount).where(UserAccount.email == email)).first()
        if not user:
            print(f"User {email} not found")
            return

        profile = session.exec(select(UserProfile).where(UserProfile.user_account_id == user.id)).first()
        if not profile:
            print(f"Profile for {email} not found")
            return

        print(f"User: {email}")
        print(f"Preferences raw: {profile.preferences}")
        try:
            prefs = json.loads(profile.preferences)
            print(f"Preferred Voice: {prefs.get('preferred_voice')}")
        except Exception as e:
            print(f"Error parsing JSON: {e}")

if __name__ == "__main__":
    # Assuming the user is the one we set up earlier or the admin
    # The user didn't specify their email in this request, but implied it was the one they logged in as (filippmiller@gmail.com)
    check_preferences("filippmiller@gmail.com")
    
    # Force update to jane
    print("\nForcing update to 'jane'...")
    with Session(engine) as session:
        user = session.exec(select(UserAccount).where(UserAccount.email == "filippmiller@gmail.com")).first()
        profile = session.exec(select(UserProfile).where(UserProfile.user_account_id == user.id)).first()
        
        prefs = json.loads(profile.preferences)
        prefs["preferred_voice"] = "jane"
        profile.preferences = json.dumps(prefs)
        
        session.add(profile)
        session.commit()
        print("Updated to jane.")
        
    check_preferences("filippmiller@gmail.com")
