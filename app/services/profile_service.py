from sqlmodel import Session, select
from app.models import UserAccount, UserProfile, UserState

def get_or_create_profile_for_user(
    db: Session,
    user: UserAccount
) -> UserProfile:
    """
    Try to find UserProfile where user_account_id == user.id.
    If found -> return it.
    If not found:
    Create a new UserProfile with:
    user_account_id = user.id
    other profile fields set to sensible defaults or None.
    Persist and return the new profile.
    """
    statement = select(UserProfile).where(UserProfile.user_account_id == user.id)
    profile = db.exec(statement).first()
    
    if profile:
        return profile
        
    # Create new profile
    new_profile = UserProfile(
        name=user.full_name or user.email.split("@")[0], # Default name from email or full_name
        english_level="A1", # Default level
        user_account_id=user.id
    )
    db.add(new_profile)
    db.commit()
    db.refresh(new_profile)
    return new_profile

def get_or_create_state_for_user(
    db: Session,
    user: UserAccount
) -> UserState:
    """
    Try to find UserState where user_account_id == user.id.
    If found -> return it.
    If not found:
    Create a new UserState with:
    user_account_id = user.id
    any JSON fields (e.g. weak_words, known_words) initialized to empty structures.
    Persist and return.
    """
    statement = select(UserState).where(UserState.user_account_id == user.id)
    state = db.exec(statement).first()
    
    if state:
        return state
        
    # We need a user_id for the foreign key to UserProfile.
    # So we must ensure a profile exists first.
    profile = get_or_create_profile_for_user(db, user)
    
    new_state = UserState(
        user_id=profile.id, # Link to the profile
        user_account_id=user.id,
        weak_words_json="[]",
        known_words_json="[]"
    )
    db.add(new_state)
    db.commit()
    db.refresh(new_state)
    return new_state
