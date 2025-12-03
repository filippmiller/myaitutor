import json
from sqlmodel import Session, select
from app.models import UserProfile, UserState, TutorSystemRule, SessionSummary
from app.security import ADMIN_EMAIL

def get_tutor_memory_for_user(session: Session, user_id: int) -> dict:
    # Get UserState
    user_state = session.exec(select(UserState).where(UserState.user_id == user_id)).first()
    
    # Get last session summary
    # Assuming we want the most recent one
    last_summary = session.exec(
        select(SessionSummary)
        .where(SessionSummary.user_account_id == user_state.user_account_id) # Note: SessionSummary uses user_account_id
        .order_by(SessionSummary.created_at.desc())
    ).first()

    memory = {
        "weak_words": user_state.weak_words if user_state else [],
        "known_words_count": len(user_state.known_words) if user_state else 0,
        "xp": user_state.xp_points if user_state else 0,
        "last_summary": last_summary.summary_text if last_summary else None
    }
    return memory

def build_tutor_system_prompt(session: Session, user: UserProfile) -> str:
    # 1. Fetch System Rules
    rules = session.exec(select(TutorSystemRule).where(TutorSystemRule.enabled == True).order_by(TutorSystemRule.sort_order)).all()
    
    # 2. Fetch User Preferences
    prefs = json.loads(user.preferences)
    preferred_address = prefs.get("preferred_address")
    
    # 3. Fetch Memory
    memory = get_tutor_memory_for_user(session, user.id)
    
    # 4. Construct Prompt
    prompt_parts = []
    
    # Base Identity
    prompt_parts.append("You are a personal English tutor for a Russian-speaking student.")
    
    # System Rules
    if rules:
        prompt_parts.append("\nSystem Rules:")
        for rule in rules:
            prompt_parts.append(f"- {rule.rule_text}")
            
    # Personalization
    prompt_parts.append("\nStudent Context:")
    prompt_parts.append(f"Name: {user.name}")
    prompt_parts.append(f"Level: {user.english_level}")
    if preferred_address:
        prompt_parts.append(f"Preferred Address: {preferred_address}")
    else:
        prompt_parts.append("Preferred Address: Not set. You should politely ask for it in the first message.")
        
    # Memory
    prompt_parts.append("\nMemory:")
    if memory["last_summary"]:
        prompt_parts.append(f"Last Lesson Summary: {memory['last_summary']}")
    if memory["weak_words"]:
        prompt_parts.append(f"Weak Words to Practice: {', '.join(memory['weak_words'])}")
        
    # Standard Instructions (can be partially replaced by rules, but keeping core logic here)
    prompt_parts.append("""
Behavior:
- Speak slowly and clearly.
- Adapt to the student's level.
- If the student makes a mistake, correct it gently and explain briefly.
- Answer primarily in English, but use Russian for complex explanations if needed.
""")

    return "\n".join(prompt_parts)
