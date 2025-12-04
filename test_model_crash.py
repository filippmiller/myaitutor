from app.models import LessonSession
from datetime import datetime
import sys

try:
    print("Attempting to create LessonSession with None user_account_id...")
    session = LessonSession(
        user_account_id=None,
        started_at=datetime.utcnow()
    )
    print("Success! (Unexpected)")
except Exception as e:
    print(f"Caught expected exception: {type(e).__name__}: {e}")
    sys.exit(0)
