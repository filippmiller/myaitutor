import json
from datetime import datetime
from sqlmodel import Session
from app.models import UserState, SessionSummary, UserAccount

def load_words(json_str: str | None) -> list[str]:
    """Load list of strings from JSON string. Returns empty list if None or invalid."""
    if not json_str:
        return []
    try:
        data = json.loads(json_str)
        if isinstance(data, list):
            return [str(x) for x in data]
        return []
    except json.JSONDecodeError:
        return []

def dump_words(words: list[str]) -> str:
    """Dump list of strings to JSON string."""
    return json.dumps(words)

def merge_words(base: list[str], new: list[str], max_size: int | None = None) -> list[str]:
    """Merge new words into base list, avoiding duplicates. Optionally truncate."""
    # Use a dict to preserve order while removing duplicates (Python 3.7+)
    existing = {w: True for w in base}
    for w in new:
        if w and w not in existing:
            base.append(w)
            existing[w] = True
    
    if max_size is not None and len(base) > max_size:
        # Keep the most recent ones? Or the first ones?
        # Usually for "known words" we might want to keep all, but for "weak words" maybe most recent.
        # Let's just keep the first N for now as a simple heuristic, or maybe last N?
        # The prompt says "reasonable max length".
        # Let's keep the *last* N added if we assume append adds to end.
        return base[-max_size:]
    return base

def apply_learning_update(
    db: Session,
    state: UserState,
    analysis: dict
) -> None:
    """
    Update UserState based on analysis results.
    analysis dict structure:
    {
        "new_known_words": [...],
        "new_weak_words": [...],
        "xp_delta": int,
        "grammar_notes": [...],
    }
    """
    # 1. Update words
    current_known = load_words(state.known_words_json)
    new_known = analysis.get("new_known_words", [])
    merged_known = merge_words(current_known, new_known, max_size=500)
    state.known_words_json = dump_words(merged_known)

    current_weak = load_words(state.weak_words_json)
    new_weak = analysis.get("new_weak_words", [])
    merged_weak = merge_words(current_weak, new_weak, max_size=100)
    state.weak_words_json = dump_words(merged_weak)

    # 2. Update counters
    state.session_count += 1
    # Assuming 2 messages per interaction (User + Assistant)
    state.total_messages += 2 
    state.xp_points += analysis.get("xp_delta", 1)
    state.last_session_at = datetime.utcnow()

    db.add(state)
    db.commit()
    db.refresh(state)

def create_session_summary(
    db: Session,
    user: UserAccount,
    analysis: dict
) -> SessionSummary:
    """
    Create a SessionSummary record.
    analysis dict also contains:
    - "session_summary": str | None
    - "practiced_words": list[str]
    - "new_weak_words": list[str]
    - "grammar_notes": list[str]
    """
    summary = SessionSummary(
        user_account_id=user.id,
        summary_text=analysis.get("session_summary"),
        practiced_words_json=dump_words(analysis.get("practiced_words", [])),
        weak_words_json=dump_words(analysis.get("new_weak_words", [])),
        grammar_notes_json=dump_words(analysis.get("grammar_notes", []))
    )
    db.add(summary)
    db.commit()
    db.refresh(summary)
    return summary
