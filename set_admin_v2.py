import os
from sqlmodel import Session, select
from app.database import engine
from app.models import UserAccount

# Hardcoded for this specific request to ensure it works regardless of env var
TARGET_EMAIL = "filippmiller@gmail.com"

def set_admin_role():
    print(f"Setting admin role for {TARGET_EMAIL}...")
    with Session(engine) as session:
        user = session.exec(select(UserAccount).where(UserAccount.email == TARGET_EMAIL)).first()
        if user:
            user.role = "admin"
            session.add(user)
            session.commit()
            session.refresh(user)
            print(f"Successfully set role='admin' for user {user.email} (ID: {user.id})")
        else:
            print(f"User with email {TARGET_EMAIL} not found. Please register first.")

if __name__ == "__main__":
    set_admin_role()
