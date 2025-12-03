#!/usr/bin/env python3
"""
Script to apply conversation persistence to voice_ws.py
"""

# Read the original file
with open('app/api/voice_ws.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Prepare modifications
new_lines = []

for i, line in enumerate(lines, 1):
    # 1. Add imports after line 17
    if i == 18:
        new_lines.append(line.replace(
            'from app.models import AppSettings, UserAccount, UserProfile, AuthSession',
            'from app.models import AppSettings, UserAccount, UserProfile, AuthSession, LessonSession, LessonTurn'
        ))
        continue
    
    # 2. Add datetime import after line 19
    if i == 20 and 'from collections import deque' in line:
        new_lines.append(line)
        new_lines.append('from datetime import datetime, timedelta\n')
        continue
        
    # 3. Insert ConversationTracker class after get_latency_stats (after line 40)
    if i == 41 and 'router = APIRouter()' in line:
        tracker_code = '''
# Conversation persistence helper
class ConversationTracker:
    """Tracks and persists conversation turns to the database."""
    def __init__(self, db_session, user_account_id):
        self.db_session = db_session
        self.user_account_id = user_account_id
        self.lesson_session = None
        self.turn_buffer = []
        
    def start_session(self):
        if self.user_account_id:
            self.lesson_session = LessonSession(
                user_account_id=self.user_account_id,
                started_at=datetime.utcnow(),
                status="active"
            )
            self.db_session.add(self.lesson_session)
            self.db_session.commit()
            self.db_session.refresh(self.lesson_session)
            logger.info(f"Started lesson session {self.lesson_session.id}")
    
    def add_turn(self, speaker, text):
        if self.lesson_session and text.strip():
            turn = LessonTurn(
                session_id=self.lesson_session.id,
                speaker=speaker,
                text=text,
                created_at=datetime.utcnow()
            )
            self.turn_buffer.append(turn)
            if len(self.turn_buffer) >= 5:
                self.flush()
    
    def flush(self):
        if self.turn_buffer:
            self.db_session.add_all(self.turn_buffer)
            self.db_session.commit()
            logger.info(f"Saved {len(self.turn_buffer)} turns to DB")
            self.turn_buffer = []
    
    def end_session(self):
        if self.lesson_session:
            self.flush()
            self.lesson_session.ended_at = datetime.utcnow()
            self.lesson_session.duration_seconds = int(
                (self.lesson_session.ended_at - self.lesson_session.started_at).total_seconds()
            )
            self.lesson_session.status = "completed"
            self.db_session.commit()
            logger.info(f"Ended lesson session {self.lesson_session.id}")

'''
        new_lines.append(tracker_code)
        new_lines.append(line)
        continue
    
    new_lines.append(line)

# Write back
with open('app/api/voice_ws.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print("Applied conversation persistence infrastructure")
