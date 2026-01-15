"""
Smart Brain Service for AIlingva

This service provides INTELLIGENT analysis of student conversations using LLM,
replacing the old string-matching approach with actual understanding.

Key capabilities:
1. Detect weak words and WHY they're weak (pronunciation, meaning, usage)
2. Identify grammar patterns and specific mistakes
3. Generate dynamic rules based on student needs
4. Plan next activities based on accumulated knowledge
5. Assess level changes in real-time

The brain runs asynchronously alongside the streaming pipeline.
"""

import asyncio
import json
import logging
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime
from dataclasses import dataclass, asdict
from enum import Enum

from sqlmodel import Session, select
from openai import AsyncOpenAI

from app.models import (
    TutorLessonTurn,
    TutorBrainEvent,
    TutorStudentKnowledge,
    TutorRule,
    UserAccount,
    AppSettings,
)

logger = logging.getLogger(__name__)


# ============================================================
# Data Classes for Brain Analysis Results
# ============================================================

class WeakWordReason(str, Enum):
    PRONUNCIATION = "pronunciation"
    MEANING = "meaning"
    USAGE = "usage"
    GRAMMAR = "grammar"
    SPELLING = "spelling"


@dataclass
class WeakWordDetection:
    word: str
    reason: WeakWordReason
    context: str
    suggestion: str


@dataclass
class GrammarIssue:
    pattern: str  # e.g., "past_simple", "articles", "prepositions"
    mistake: str  # What the student said
    correction: str  # What they should have said
    explanation: str  # Brief explanation


@dataclass
class LevelAssessment:
    current_estimate: str  # CEFR level
    confidence: float  # 0.0 - 1.0
    evidence: str  # Why this assessment


@dataclass
class SuggestedRule:
    type: str  # greeting, practice, focus, etc.
    description: str
    priority: int
    trigger: Optional[str] = None


@dataclass
class BrainAnalysisResult:
    weak_words: List[WeakWordDetection]
    grammar_issues: List[GrammarIssue]
    level_assessment: Optional[LevelAssessment]
    suggested_rules: List[SuggestedRule]
    topics_detected: List[str]
    student_mood: str  # confident, struggling, frustrated, engaged
    next_activity_hint: Optional[str]


# ============================================================
# Analysis Prompts
# ============================================================

ANALYSIS_SYSTEM_PROMPT = """You are an expert English language analyst for a tutoring system.

Analyze the conversation exchange and return a JSON object with your findings.

Be STRICT and PRECISE:
- Only mark words as weak if the student ACTUALLY made a mistake or showed confusion
- Only identify grammar issues that ACTUALLY occurred
- Base level assessment on EVIDENCE from the conversation
- Suggested rules should be SPECIFIC and ACTIONABLE

Return ONLY valid JSON, no explanations outside the JSON.
"""

ANALYSIS_USER_PROMPT_TEMPLATE = """Analyze this tutoring exchange:

STUDENT (level estimate: {level}): "{user_text}"
TUTOR RESPONSE: "{tutor_text}"

Context:
- Current known weak words: {weak_words}
- Topics being practiced: {topics}
- Language mode: {language_mode}

Return JSON with this exact structure:
{{
  "weak_words": [
    {{
      "word": "string",
      "reason": "pronunciation|meaning|usage|grammar|spelling",
      "context": "what happened",
      "suggestion": "how to help"
    }}
  ],
  "grammar_issues": [
    {{
      "pattern": "e.g. past_simple, articles, prepositions",
      "mistake": "what student said",
      "correction": "correct form",
      "explanation": "brief explanation"
    }}
  ],
  "level_assessment": {{
    "current_estimate": "A1|A2|B1|B2|C1|C2",
    "confidence": 0.0-1.0,
    "evidence": "why this assessment"
  }} or null if not enough data,
  "suggested_rules": [
    {{
      "type": "practice|focus|avoid|encourage",
      "description": "specific instruction for tutor",
      "priority": 1-5
    }}
  ],
  "topics_detected": ["list", "of", "topics"],
  "student_mood": "confident|struggling|frustrated|engaged|neutral",
  "next_activity_hint": "suggestion for next activity" or null
}}

IMPORTANT:
- If student made NO mistakes, return empty arrays
- Only include level_assessment if you have clear evidence
- Be conservative - don't over-diagnose issues
"""


# ============================================================
# Smart Brain Service
# ============================================================

class SmartBrainService:
    """
    Intelligent brain service that uses LLM for analysis.

    Can run both synchronously and asynchronously.
    """

    def __init__(
        self,
        session: Session,
        api_key: Optional[str] = None,
        model: str = "gpt-4o-mini",
    ):
        self.session = session
        self.model = model

        # Get API key from settings if not provided
        if api_key:
            self.api_key = api_key
        else:
            settings = session.get(AppSettings, 1)
            self.api_key = settings.openai_api_key if settings else None

        if not self.api_key:
            logger.warning("SmartBrainService initialized without API key")

    async def analyze_turn_async(
        self,
        turn: TutorLessonTurn,
        user: UserAccount,
        context: Optional[Dict[str, Any]] = None,
    ) -> BrainAnalysisResult:
        """
        Analyze a conversation turn using LLM.

        Args:
            turn: The conversation turn to analyze
            user: The user account
            context: Additional context (weak_words, topics, language_mode)

        Returns:
            BrainAnalysisResult with all findings
        """
        if not self.api_key:
            logger.error("Cannot analyze: no API key")
            return self._empty_result()

        if not turn.user_text:
            return self._empty_result()

        # Prepare context
        context = context or {}
        knowledge = self.session.get(TutorStudentKnowledge, user.id)

        weak_words = []
        if knowledge:
            weak_words = [
                w.get("word") if isinstance(w, dict) else w
                for w in knowledge.vocabulary_json.get("weak", [])
            ][:10]

        prompt = ANALYSIS_USER_PROMPT_TEMPLATE.format(
            level=knowledge.level if knowledge else "A1",
            user_text=turn.user_text,
            tutor_text=turn.tutor_text or "(no response yet)",
            weak_words=", ".join(weak_words) if weak_words else "none",
            topics=", ".join(context.get("topics", [])) if context.get("topics") else "general",
            language_mode=context.get("language_mode", "MIXED"),
        )

        try:
            client = AsyncOpenAI(api_key=self.api_key)

            response = await client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": ANALYSIS_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,  # Lower temperature for more consistent analysis
                max_tokens=1000,
                response_format={"type": "json_object"},
            )

            result_json = response.choices[0].message.content
            result = self._parse_analysis_result(result_json)

            logger.info(
                f"Brain analysis complete: {len(result.weak_words)} weak words, "
                f"{len(result.grammar_issues)} grammar issues"
            )

            return result

        except Exception as e:
            logger.error(f"Brain analysis failed: {e}", exc_info=True)
            return self._empty_result()

    def analyze_turn_sync(
        self,
        turn: TutorLessonTurn,
        user: UserAccount,
        context: Optional[Dict[str, Any]] = None,
    ) -> BrainAnalysisResult:
        """
        Synchronous wrapper for analyze_turn_async.
        """
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If we're already in an async context, create a new task
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run,
                        self.analyze_turn_async(turn, user, context)
                    )
                    return future.result(timeout=10)
            else:
                return loop.run_until_complete(
                    self.analyze_turn_async(turn, user, context)
                )
        except Exception as e:
            logger.error(f"Sync analysis failed: {e}")
            return self._empty_result()

    def _parse_analysis_result(self, json_str: str) -> BrainAnalysisResult:
        """Parse JSON response into BrainAnalysisResult."""
        try:
            data = json.loads(json_str)

            weak_words = []
            for w in data.get("weak_words", []):
                try:
                    weak_words.append(WeakWordDetection(
                        word=w.get("word", ""),
                        reason=WeakWordReason(w.get("reason", "usage")),
                        context=w.get("context", ""),
                        suggestion=w.get("suggestion", ""),
                    ))
                except:
                    pass

            grammar_issues = []
            for g in data.get("grammar_issues", []):
                try:
                    grammar_issues.append(GrammarIssue(
                        pattern=g.get("pattern", ""),
                        mistake=g.get("mistake", ""),
                        correction=g.get("correction", ""),
                        explanation=g.get("explanation", ""),
                    ))
                except:
                    pass

            level_assessment = None
            if data.get("level_assessment"):
                la = data["level_assessment"]
                level_assessment = LevelAssessment(
                    current_estimate=la.get("current_estimate", "A1"),
                    confidence=float(la.get("confidence", 0.5)),
                    evidence=la.get("evidence", ""),
                )

            suggested_rules = []
            for r in data.get("suggested_rules", []):
                try:
                    suggested_rules.append(SuggestedRule(
                        type=r.get("type", "practice"),
                        description=r.get("description", ""),
                        priority=int(r.get("priority", 3)),
                        trigger=r.get("trigger"),
                    ))
                except:
                    pass

            return BrainAnalysisResult(
                weak_words=weak_words,
                grammar_issues=grammar_issues,
                level_assessment=level_assessment,
                suggested_rules=suggested_rules,
                topics_detected=data.get("topics_detected", []),
                student_mood=data.get("student_mood", "neutral"),
                next_activity_hint=data.get("next_activity_hint"),
            )

        except Exception as e:
            logger.error(f"Failed to parse analysis result: {e}")
            return self._empty_result()

    def _empty_result(self) -> BrainAnalysisResult:
        """Return an empty result when analysis fails or is skipped."""
        return BrainAnalysisResult(
            weak_words=[],
            grammar_issues=[],
            level_assessment=None,
            suggested_rules=[],
            topics_detected=[],
            student_mood="neutral",
            next_activity_hint=None,
        )

    def save_analysis_to_db(
        self,
        result: BrainAnalysisResult,
        turn: TutorLessonTurn,
        user_id: int,
    ) -> List[TutorBrainEvent]:
        """
        Save analysis results to database as brain events.

        Returns list of created events.
        """
        events = []

        # 1. Save weak words
        for ww in result.weak_words:
            event = TutorBrainEvent(
                lesson_id=turn.lesson_id,
                user_id=user_id,
                turn_id=turn.id,
                pipeline_type="ANALYSIS",
                event_type="WEAK_WORD_DETECTED",
                event_payload_json=asdict(ww),
            )
            self.session.add(event)
            events.append(event)

        # 2. Save grammar issues
        for gi in result.grammar_issues:
            event = TutorBrainEvent(
                lesson_id=turn.lesson_id,
                user_id=user_id,
                turn_id=turn.id,
                pipeline_type="ANALYSIS",
                event_type="GRAMMAR_ISSUE_DETECTED",
                event_payload_json=asdict(gi),
            )
            self.session.add(event)
            events.append(event)

        # 3. Save level assessment if present
        if result.level_assessment:
            event = TutorBrainEvent(
                lesson_id=turn.lesson_id,
                user_id=user_id,
                turn_id=turn.id,
                pipeline_type="ANALYSIS",
                event_type="LEVEL_ASSESSMENT",
                event_payload_json=asdict(result.level_assessment),
            )
            self.session.add(event)
            events.append(event)

        # 4. Create suggested rules as TutorRule entries
        for sr in result.suggested_rules:
            if sr.priority >= 4:  # Only save high-priority suggestions
                rule = TutorRule(
                    scope="session",
                    type=sr.type,
                    title=f"Brain suggestion: {sr.type}",
                    description=sr.description,
                    priority=sr.priority,
                    is_active=True,
                    applies_to_student_id=user_id,
                    created_by="smart_brain",
                    updated_by="smart_brain",
                    source="brain_analysis",
                )
                self.session.add(rule)

        # 5. Update student knowledge
        knowledge = self.session.get(TutorStudentKnowledge, user_id)
        if knowledge:
            # Add weak words
            current_weak = knowledge.vocabulary_json.get("weak", [])
            for ww in result.weak_words:
                exists = any(
                    (isinstance(w, dict) and w.get("word") == ww.word) or w == ww.word
                    for w in current_weak
                )
                if not exists:
                    current_weak.append({
                        "word": ww.word,
                        "reason": ww.reason.value,
                        "frequency": 1,
                        "added_at": datetime.utcnow().isoformat(),
                    })
            knowledge.vocabulary_json["weak"] = current_weak

            # Update grammar patterns
            patterns = knowledge.grammar_json.get("patterns", {})
            for gi in result.grammar_issues:
                if gi.pattern not in patterns:
                    patterns[gi.pattern] = {"attempts": 0, "mistakes": 0, "mastery": 0.0}
                patterns[gi.pattern]["mistakes"] += 1
                patterns[gi.pattern]["attempts"] += 1
                # Recalculate mastery
                p = patterns[gi.pattern]
                p["mastery"] = 1.0 - (p["mistakes"] / max(p["attempts"], 1))
            knowledge.grammar_json["patterns"] = patterns

            # Update level if confident assessment
            if result.level_assessment and result.level_assessment.confidence >= 0.7:
                knowledge.level = result.level_assessment.current_estimate

            knowledge.updated_at = datetime.utcnow()
            self.session.add(knowledge)

        self.session.commit()

        logger.info(f"Saved {len(events)} brain events to database")
        return events


# ============================================================
# Async Brain Worker
# ============================================================

class AsyncBrainWorker:
    """
    Worker that processes turns in the background.

    This allows the brain to run asynchronously without blocking
    the streaming pipeline.
    """

    def __init__(self, session: Session, api_key: str):
        self.brain = SmartBrainService(session, api_key)
        self.queue: asyncio.Queue = asyncio.Queue()
        self.running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self):
        """Start the background worker."""
        if self.running:
            return
        self.running = True
        self._task = asyncio.create_task(self._process_loop())
        logger.info("AsyncBrainWorker started")

    async def stop(self):
        """Stop the background worker."""
        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("AsyncBrainWorker stopped")

    async def submit_turn(
        self,
        turn: TutorLessonTurn,
        user: UserAccount,
        context: Optional[Dict[str, Any]] = None,
    ):
        """Submit a turn for background analysis."""
        await self.queue.put((turn, user, context))
        logger.debug(f"Turn {turn.id} submitted for brain analysis")

    async def _process_loop(self):
        """Main processing loop."""
        while self.running:
            try:
                # Wait for items with timeout
                try:
                    turn, user, context = await asyncio.wait_for(
                        self.queue.get(),
                        timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue

                # Process the turn
                try:
                    result = await self.brain.analyze_turn_async(turn, user, context)
                    self.brain.save_analysis_to_db(result, turn, user.id)
                except Exception as e:
                    logger.error(f"Brain analysis error: {e}", exc_info=True)

                self.queue.task_done()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Brain worker error: {e}", exc_info=True)
