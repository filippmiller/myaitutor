import os
from sqlmodel import Session, select
from app.database import engine
from app.models import UserAccount
from app.security import ADMIN_EMAIL

def set_admin_role():
    print(f"Setting admin role for {ADMIN_EMAIL}...")
    with Session(engine) as session:
        user = session.exec(select(UserAccount).where(UserAccount.email == ADMIN_EMAIL)).first()
        if user:
            user.role = "admin"
            session.add(user)
            session.commit()
            print(f"Successfully set role='admin' for user {user.email} (ID: {user.id})")
        else:
            print(f"User with email {ADMIN_EMAIL} not found. Please register first.")

if __name__ == "__main__":
    set_admin_role()
