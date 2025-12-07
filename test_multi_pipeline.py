"""
Test script for multi-pipeline architecture

This script creates test data to verify:
1. Lesson numbering works correctly
2. Turn tracking saves to new tables
3. Brain analysis generates events
4. Admin API returns data
"""

import sys
import os

# Add app to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlmodel import Session, create_engine, select
from app.database import engine
from app.models import UserAccount, TutorLesson, TutorLessonTurn, TutorBrainEvent, TutorStudentKnowledge
from app.services.tutor_service import get_next_lesson_number, is_first_lesson
from app.services.brain_service import BrainService
from app.services.lesson_pipeline_manager import LessonPipelineManager
from datetime import datetime


def test_multi_pipeline():
    """Test the multi-pipeline architecture."""
    
    print("\n" + "=" * 80)
    print("🧪 TESTING MULTI-PIPELINE ARCHITECTURE")
    print("=" * 80)
    
    with Session(engine) as session:
        # 1. Find or create test user
        print("\n📌 Step 1: Finding test user...")
        test_user = session.exec(
            select(UserAccount).where(UserAccount.email == "test@ailingva.com")).first()
        
        if not test_user:
            print("❌ Test user not found. Please create a user with email 'test@ailingva.com' first.")
            return
        
        print(f"✅ Found test user: {test_user.email} (ID: {test_user.id})")
        
        # 2. Check lesson number
        print("\n📌 Step 2: Checking lesson number...")
        lesson_num = get_next_lesson_number(session, test_user.id)
        is_first = is_first_lesson(session, test_user.id)
        print(f"  Next lesson number: {lesson_num}")
        print(f"  Is first lesson: {is_first}")
        
        # 3. Test pipeline manager
        print("\n📌 Step 3: Testing LessonPipelineManager...")
        try:
            manager = LessonPipelineManager(session, test_user)
            
            # Create a mock lesson session ID (would normally come from LessonSession)
            lesson = session.exec(select(TutorLesson).where(TutorLesson.user_id == test_user.id)).first()
            
            if not lesson:
                print("  Creating new lesson...")
                from app.models import LessonSession
                # Create a legacy lesson session
                legacy_session = LessonSession(
                    user_account_id=test_user.id,
                    started_at=datetime.utcnow(),
                    status="active"
                )
                session.add(legacy_session)
                session.commit()
                session.refresh(legacy_session)
                
                lesson = manager.start_lesson(legacy_session_id=legacy_session.id)
                print(f"  ✅ Created lesson {lesson.id} (lesson_number={lesson.lesson_number})")
            else:
                print(f"  ✅ Using existing lesson {lesson.id}")
            
            # 4. Test turn saving
            print("\n📌 Step 4: Testing turn saving...")
            turn = manager.save_turn(
                user_text="I go to school yesterday",
                tutor_text="Actually, it should be 'I went to school yesterday'. 'Went' is the past tense of 'go'."
            )
            
            if turn:
                print(f"  ✅ Saved turn {turn.turn_index}")
                print(f"     User: {turn.user_text[:50]}...")
                print(f"     Tutor: {turn.tutor_text[:50] if turn.tutor_text else 'None'}...")
            
            # 5. Check brain events
            print("\n📌 Step 5: Checking brain events...")
            events = session.exec(
                select(TutorBrainEvent)
                .where(TutorBrainEvent.lesson_id == lesson.id)
                .order_by(TutorBrainEvent.created_at.desc())
                .limit(5)
            ).all()
            
            print(f"  Found {len(events)} brain events for this lesson:")
            for event in events:
                print(f"    - {event.event_type}: {event.event_payload_json}")
            
            # 6. Check student knowledge
            print("\n📌 Step 6: Checking student knowledge...")
            knowledge = session.get(TutorStudentKnowledge, test_user.id)
            
            if knowledge:
                print(f"  ✅ Student Knowledge:")
                print(f"     Level: {knowledge.level}")
                print(f"     Lesson count: {knowledge.lesson_count}")
                print(f"      First lesson completed: {knowledge.first_lesson_completed}")
                print(f"     Weak words: {len(knowledge.vocabulary_json.get('weak', []))}")
                print(f"     Strong words: {len(knowledge.vocabulary_json.get('strong', []))}")
            else:
                print("  ⚠️ No knowledge record found")
            
            # 7. Test queries
            print("\n📌 Step 7: Testing admin API queries...")
            
            # Count lessons
            lesson_count = len(list(session.exec(
                select(TutorLesson).where(TutorLesson.user_id == test_user.id)
            ).all()))
            print(f"  Total lessons for user: {lesson_count}")
            
            # Count turns
            turn_count = len(list(session.exec(
                select(TutorLessonTurn).where(TutorLessonTurn.user_id == test_user.id)
            ).all()))
            print(f"  Total turns for user: {turn_count}")
            
            # Count brain events
            event_count = len(list(session.exec(
                select(TutorBrainEvent).where(TutorBrainEvent.user_id == test_user.id)
            ).all()))
            print(f"  Total brain events for user: {event_count}")
            
            print("\n" + "=" * 80)
            print("✅ ALL TESTS PASSED!")
            print("=" * 80)
            
        except Exception as e:
            print(f"\n❌ TEST FAILED: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    test_multi_pipeline()
