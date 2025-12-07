from sqlmodel import Session, select
from app.models import UserAccount, UserProfile, UserState
from datetime import datetime
import json

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

def map_scale_to_cefr(score: int) -> str:
    """Map self-assessed 1–10 scale to a coarse CEFR-like label.

    This is intentionally simple and only used to fill UserProfile.english_level
    from onboarding data when the student rates themselves.
    """
    if score <= 1:
        return "A0"
    if score == 2:
        return "A1-"
    if score == 3:
        return "A1/A2"
    if score == 4:
        return "A2"
    if score == 5:
        return "B1-"
    if score == 6:
        return "B1/B2"
    if score == 7:
        return "B2"
    if score == 8:
        return "B2/C1"
    if score == 9:
        return "C1"
    return "C2"

def apply_intro_profile_updates(
    db: Session,
    profile: UserProfile,
    transcript: str,
) -> None:
    """Parse [PROFILE_UPDATE] markers from an assistant transcript and update profile.

    The tutor emits lines of the form:
      [PROFILE_UPDATE] {"field": value, ...}

    We extract all such JSON objects and merge them into `profile.preferences`
    under the `intro` key, updating core `UserProfile` fields where appropriate.
    Errors in individual JSON snippets are ignored so that a bad marker does not
    break the lesson.
    """
    if not transcript:
        return

    updates: list[dict] = []
    for raw_line in transcript.splitlines():
        line = raw_line.strip()
        if not line.startswith("[PROFILE_UPDATE]"):
            continue
        json_part = line[len("[PROFILE_UPDATE]") :].strip()
        if not json_part:
            continue
        try:
            obj = json.loads(json_part)
            if isinstance(obj, dict):
                updates.append(obj)
        except json.JSONDecodeError:
            # Skip malformed marker but keep processing others
            continue

    if not updates:
        return

    # Load existing prefs + intro block
    try:
        prefs = json.loads(profile.preferences)
    except Exception:
        prefs = {}

    intro = prefs.get("intro") or {}
    changed = False

    for upd in updates:
        for key, value in upd.items():
            if key in ("student_name", "name"):
                if isinstance(value, str) and value.strip():
                    name = value.strip()
                    intro["student_name"] = name
                    # Also keep primary profile.name in sync
                    profile.name = name
                    changed = True

            elif key == "tutor_name":
                if isinstance(value, str) and value.strip():
                    intro["tutor_name"] = value.strip()
                    changed = True

            elif key == "age":
                try:
                    age_int = int(value)
                except (TypeError, ValueError):
                    continue
                if 5 <= age_int <= 100:
                    intro["age"] = age_int
                    intro["age_is_unknown"] = False
                    changed = True

            elif key == "age_is_unknown":
                flag = bool(value)
                intro["age_is_unknown"] = flag
                if flag:
                    intro.pop("age", None)
                changed = True

            elif key == "addressing_mode":
                if value in ("ty", "vy"):
                    intro["addressing_mode"] = value
                    changed = True

            elif key == "conversation_style":
                if value in ("formal", "informal"):
                    intro["conversation_style"] = value
                    changed = True

            elif key == "humor_allowed":
                intro["humor_allowed"] = bool(value)
                changed = True

            elif key == "english_level_scale_1_10":
                try:
                    score = int(value)
                except (TypeError, ValueError):
                    continue
                if score < 1:
                    score = 1
                if score > 10:
                    score = 10
                intro["english_level_scale_1_10"] = score
                # Map to CEFR-ish label for main profile field
                profile.english_level = map_scale_to_cefr(score)
                changed = True

            elif key == "goals":
                if isinstance(value, list):
                    goals = [str(g) for g in value if str(g).strip()]
                    intro["goals"] = goals
                    # For compatibility, also store a simple text version
                    if goals:
                        profile.goals = ", ".join(goals)
                    changed = True

            elif key == "topics_interest":
                if isinstance(value, list):
                    intro["topics_interest"] = [str(t) for t in value if str(t).strip()]
                    changed = True

            elif key == "native_language":
                if isinstance(value, str) and value.strip():
                    intro["native_language"] = value.strip()
                    changed = True

            elif key == "other_languages":
                if isinstance(value, list):
                    intro["other_languages"] = [str(l) for l in value if str(l).strip()]
                    changed = True

            elif key == "correction_style":
                if value in ("often", "on_request", "soft"):
                    intro["correction_style"] = value
                    changed = True

            elif key in ("intro_completed", "completed"):
                if bool(value):
                    intro["intro_completed"] = True
                    # If version is not set, use provided or default to v1
                    version = upd.get("intro_version") or intro.get("intro_version") or "v1"
                    intro["intro_version"] = str(version)
                    intro["intro_completed_at"] = datetime.utcnow().isoformat()
                    changed = True

            elif key == "intro_version":
                if value:
                    intro["intro_version"] = str(value)
                    changed = True

            else:
                # For any other fields we don't specifically know about, store
                # them inside intro as-is; this makes the protocol forward-compatible.
                intro[key] = value
                changed = True

    if not changed:
        return

    prefs["intro"] = intro
    profile.preferences = json.dumps(prefs, ensure_ascii=False)
    db.add(profile)
    db.commit()
    db.refresh(profile)
