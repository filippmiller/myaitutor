"""
Session Rule Manager for AIlingva

This module provides real-time rule management for active tutoring sessions.
It solves the core problem of rules being "forgotten" mid-conversation by:
1. Extracting commands from user speech in real-time
2. Injecting rules into the active OpenAI conversation as system messages
3. Periodically reminding the model of active rules

The key insight: OpenAI's Realtime API maintains context, but LLMs naturally
"forget" instructions as conversation grows. We combat this by:
- Detecting preferences (language, pace) and creating explicit rules
- Injecting rules as system messages via conversation.item.create
- Sending periodic reminders every N turns
"""

import re
import logging
import json
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime
from sqlmodel import Session, select
from dataclasses import dataclass, field

from app.models import TutorRule, UserAccount, LessonSession

logger = logging.getLogger(__name__)


@dataclass
class ActiveRule:
    """A rule currently active in this session."""
    rule_id: Optional[int]
    type: str  # "language", "speech_pace", "correction_style", "other"
    content: str  # Human-readable rule text for injection
    value: Optional[str] = None  # Raw value (e.g., "RU_ONLY", "slow")
    priority: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)
    injected: bool = False  # Whether it's been sent to OpenAI
    reminder_count: int = 0
    is_session_only: bool = False  # True = don't persist to DB


# ============================================================
# PATTERN DEFINITIONS
# ============================================================

# Language switch patterns: (regex, target_mode, language_of_pattern)
LANGUAGE_SWITCH_PATTERNS: List[Tuple[str, str, str]] = [
    # Russian patterns for "speak Russian"
    (r"говори\s*(на)?\s*(по[- ])?русск", "RU_ONLY", "ru"),
    (r"перейди\s*(на)?\s*(по[- ])?русск", "RU_ONLY", "ru"),
    (r"давай\s*(на)?\s*(по[- ])?русск", "RU_ONLY", "ru"),
    (r"только\s*(на)?\s*(по[- ])?русск", "RU_ONLY", "ru"),
    (r"(на|по)\s*русск\w*\s*(говори|пожалуйста)?", "RU_ONLY", "ru"),
    (r"не\s+понимаю.{0,20}(англ|english)", "RU_ONLY", "ru"),
    (r"сложно\s+понимать", "RU_ONLY", "ru"),
    (r"я\s+(плохо\s+)?не\s+понимаю", "RU_ONLY", "ru"),
    (r"можешь\s*(на|по)\s*русск", "RU_ONLY", "ru"),
    (r"пожалуйста.{0,10}(на|по)\s*русск", "RU_ONLY", "ru"),
    (r"лучше\s*(на|по)\s*русск", "RU_ONLY", "ru"),
    (r"хочу.{0,10}(на|по)\s*русск", "RU_ONLY", "ru"),

    # English patterns for "speak Russian"
    (r"speak\s+(in\s+)?russian", "RU_ONLY", "en"),
    (r"switch\s+to\s+russian", "RU_ONLY", "en"),
    (r"(in|use)\s+russian\s+please", "RU_ONLY", "en"),
    (r"can\s+you\s+speak\s+russian", "RU_ONLY", "en"),
    (r"russian\s+please", "RU_ONLY", "en"),
    (r"i\s+don'?t\s+understand", "RU_ONLY", "en"),  # Implicit - if said in English during lesson, might need Russian

    # Russian patterns for "speak English"
    (r"говори\s*(на)?\s*(по[- ])?английск", "EN_ONLY", "ru"),
    (r"перейди\s*(на)?\s*английск", "EN_ONLY", "ru"),
    (r"давай\s*(на)?\s*английск", "EN_ONLY", "ru"),
    (r"только\s*(на)?\s*английск", "EN_ONLY", "ru"),
    (r"хочу.{0,10}(на)?\s*английск", "EN_ONLY", "ru"),

    # English patterns for "speak English"
    (r"speak\s+(only\s+)?(in\s+)?english", "EN_ONLY", "en"),
    (r"switch\s+to\s+english", "EN_ONLY", "en"),
    (r"only\s+english", "EN_ONLY", "en"),
    (r"let'?s\s+(speak|practice|use)\s+english", "EN_ONLY", "en"),
    (r"english\s+only", "EN_ONLY", "en"),
    (r"in\s+english\s+please", "EN_ONLY", "en"),
]

# Speech pace patterns
SLOW_SPEECH_PATTERNS: List[str] = [
    # Russian
    r"говори\s*(по)?медленн",
    r"медленн\w*\s+говори",
    r"помедленн",
    r"не\s+так\s+быстр",
    r"слишком\s+быстр",
    r"чуть\s+медленн",
    r"можешь\s+медленн",
    r"говори\s+тише",  # "speak quieter" often means slower
    r"не\s+торопись",
    r"не\s+спеши",
    r"сложно\s+успевать",
    r"не\s+успеваю",
    r"подожди",
    # English
    r"speak\s+slow(er|ly)?",
    r"slow(er)?\s*down",
    r"too\s+fast",
    r"slower\s+please",
    r"more\s+slowly",
    r"not\s+so\s+fast",
    r"can\s+you\s+slow",
    r"can'?t\s+keep\s+up",
    r"can'?t\s+follow",
    r"wait.{0,10}(fast|quick)",
    r"you'?re\s+(going\s+)?too\s+fast",
    r"hold\s+on",
    r"slow\s+it\s+down",
]

# Repeat/clarification patterns (session-only, not persisted)
REPEAT_PATTERNS: List[str] = [
    r"повтори",
    r"ещё\s+раз",
    r"что\s+ты\s+сказал",
    r"что\s+это\s+значит",
    r"не\s+расслышал",
    r"repeat",
    r"say\s+(that\s+)?again",
    r"one\s+more\s+time",
    r"can\s+you\s+repeat",
    r"what\s+did\s+you\s+say",
    r"pardon",
    r"sorry\s*\?",
    r"what\s*\?",
]

# Correction style patterns
CORRECTION_PATTERNS: List[Tuple[str, str]] = [
    (r"исправляй\s+(меня\s+)?(чаще|больше|всегда)", "frequent"),
    (r"correct\s+me\s+(more\s+)?often", "frequent"),
    (r"поправляй\s+(меня)?", "frequent"),
    (r"не\s+исправляй", "minimal"),
    (r"don'?t\s+correct", "minimal"),
    (r"меньше\s+исправ", "minimal"),
]


class SessionRuleManager:
    """
    Manages rules for an active tutoring session.

    Key responsibilities:
    1. Extract commands/preferences from user speech
    2. Maintain list of active rules
    3. Generate system message injections for OpenAI
    4. Track when to send rule reminders

    Usage:
        manager = SessionRuleManager(db, user, lesson_session)

        # On each user turn:
        injection = manager.process_user_turn(transcript)
        if injection:
            # Send to OpenAI via conversation.item.create
            await send_system_message(openai_ws, injection)
    """

    def __init__(
        self,
        db: Session,
        user: UserAccount,
        lesson_session: Optional[LessonSession] = None
    ):
        self.db = db
        self.user = user
        self.user_id = user.id
        self.lesson_session = lesson_session
        self.active_rules: List[ActiveRule] = []
        self.turn_count = 0
        self.last_reminder_turn = 0
        self.reminder_interval = 8  # Remind every N turns
        self.commands_this_session: List[Dict[str, Any]] = []  # Log of all detected commands

        # Load existing persistent rules from DB
        self._load_persistent_rules()

    def _load_persistent_rules(self):
        """Load rules from database that should be active for this user."""
        try:
            rules = self.db.exec(
                select(TutorRule)
                .where(TutorRule.is_active == True)
                .where(
                    (TutorRule.scope == "global") |
                    ((TutorRule.scope == "student") & (TutorRule.applies_to_student_id == self.user_id))
                )
                .order_by(TutorRule.priority.desc())
            ).all()

            for rule in rules:
                self.active_rules.append(ActiveRule(
                    rule_id=rule.id,
                    type=rule.type,
                    content=rule.description,
                    priority=rule.priority,
                ))

            logger.info(f"Loaded {len(self.active_rules)} persistent rules for user {self.user_id}")

            # Log high-priority rules
            for rule in self.active_rules:
                if rule.priority >= 80:
                    logger.info(f"  High-priority rule: [{rule.type}] {rule.content[:50]}...")

        except Exception as e:
            logger.error(f"Failed to load persistent rules: {e}")

    def extract_commands(self, transcript: str) -> List[Dict[str, Any]]:
        """
        Extract commands/preferences from user's speech.

        Returns list of detected commands with their types and values.
        """
        if not transcript:
            return []

        transcript_lower = transcript.lower().strip()
        commands = []

        # Check language switch patterns
        for pattern, mode, _ in LANGUAGE_SWITCH_PATTERNS:
            if re.search(pattern, transcript_lower, re.IGNORECASE | re.UNICODE):
                commands.append({
                    "type": "language",
                    "value": mode,
                    "source_text": transcript[:100],
                    "pattern": pattern,
                })
                logger.info(f"🎯 Detected LANGUAGE command: {mode} from '{transcript[:50]}...'")
                break  # Only one language command per turn

        # Check slow speech patterns
        for pattern in SLOW_SPEECH_PATTERNS:
            if re.search(pattern, transcript_lower, re.IGNORECASE | re.UNICODE):
                commands.append({
                    "type": "speech_pace",
                    "value": "slow",
                    "source_text": transcript[:100],
                    "pattern": pattern,
                })
                logger.info(f"🎯 Detected SPEECH_PACE command: slow from '{transcript[:50]}...'")
                break

        # Check repeat patterns (session-only)
        for pattern in REPEAT_PATTERNS:
            if re.search(pattern, transcript_lower, re.IGNORECASE | re.UNICODE):
                commands.append({
                    "type": "repeat",
                    "value": True,
                    "source_text": transcript[:100],
                    "session_only": True,
                })
                logger.info(f"🎯 Detected REPEAT request")
                break

        # Check correction style patterns
        for pattern, style in CORRECTION_PATTERNS:
            if re.search(pattern, transcript_lower, re.IGNORECASE | re.UNICODE):
                commands.append({
                    "type": "correction_style",
                    "value": style,
                    "source_text": transcript[:100],
                })
                logger.info(f"🎯 Detected CORRECTION_STYLE command: {style}")
                break

        # Log all commands for analytics
        self.commands_this_session.extend(commands)

        return commands

    def process_user_turn(self, transcript: str) -> Optional[str]:
        """
        Process a user turn and return any rule injection message.

        This should be called AFTER saving the user's turn to the database
        but BEFORE generating the assistant's response.

        Returns:
            Optional system message to inject into conversation, or None
        """
        self.turn_count += 1
        commands = self.extract_commands(transcript)

        injection_parts = []

        for cmd in commands:
            rule = self._add_rule_from_command(cmd)
            if rule:
                injection_parts.append(self._format_rule_injection(rule, is_new=True))

        # Check if we should send a reminder
        if self._should_send_reminder() and not injection_parts:
            reminder = self._build_reminder()
            if reminder:
                injection_parts.append(reminder)

        if injection_parts:
            return "\n\n".join(injection_parts)

        return None

    def _add_rule_from_command(self, cmd: Dict[str, Any]) -> Optional[ActiveRule]:
        """Add or update a rule based on detected command."""
        cmd_type = cmd["type"]
        cmd_value = cmd["value"]
        session_only = cmd.get("session_only", False)

        # Repeat commands don't create rules
        if cmd_type == "repeat":
            return None

        # Check if we already have this rule type
        existing_rule = None
        for rule in self.active_rules:
            if rule.type == cmd_type:
                existing_rule = rule
                break

        # Build rule content based on type and value
        content = self._build_rule_content(cmd_type, cmd_value)
        if not content:
            return None

        if existing_rule:
            # Update existing rule
            if existing_rule.value != cmd_value:
                existing_rule.content = content
                existing_rule.value = cmd_value
                existing_rule.injected = False  # Mark for re-injection
                existing_rule.created_at = datetime.utcnow()

                if not session_only:
                    self._persist_rule(existing_rule)

                logger.info(f"Updated existing {cmd_type} rule to: {cmd_value}")
                return existing_rule
            else:
                # Same value, just mark for reminder
                existing_rule.injected = False
                return existing_rule
        else:
            # Create new rule
            new_rule = ActiveRule(
                rule_id=None,
                type=cmd_type,
                content=content,
                value=cmd_value,
                priority=self._get_rule_priority(cmd_type),
                is_session_only=session_only,
            )
            self.active_rules.append(new_rule)

            if not session_only:
                self._persist_rule(new_rule)

            logger.info(f"Created new {cmd_type} rule: {cmd_value}")
            return new_rule

    def _build_rule_content(self, rule_type: str, value: str) -> Optional[str]:
        """Build human-readable rule content for injection."""
        if rule_type == "language":
            if value == "RU_ONLY":
                return (
                    "🚨 LANGUAGE: SPEAK RUSSIAN (говори по-русски). "
                    "Use Russian for ALL explanations and conversation. "
                    "English ONLY for teaching new vocabulary words. "
                    "Format vocabulary as: 'Слово \"apple\" означает \"яблоко\"'. "
                    "DO NOT switch back to English unless student explicitly asks."
                )
            elif value == "EN_ONLY":
                return (
                    "🚨 LANGUAGE: SPEAK ENGLISH. "
                    "Use English for everything. "
                    "Russian ONLY if student is completely stuck (1-2 words max). "
                    "DO NOT switch to Russian unless student explicitly asks."
                )

        elif rule_type == "speech_pace":
            return (
                "🚨 SPEECH PACE: SPEAK SLOWLY (говори медленно). "
                "Use '...' for pauses between phrases. "
                "Give student time to process each sentence. "
                "Example: 'The cat... is sitting... on the table.' "
                "DO NOT speed up unless student explicitly asks."
            )

        elif rule_type == "correction_style":
            if value == "frequent":
                return (
                    "CORRECTION STYLE: Correct student's mistakes frequently. "
                    "Point out grammar and pronunciation errors gently."
                )
            elif value == "minimal":
                return (
                    "CORRECTION STYLE: Minimize corrections. "
                    "Focus on fluency over accuracy. Only correct critical errors."
                )

        return None

    def _get_rule_priority(self, rule_type: str) -> int:
        """Get default priority for a rule type."""
        priorities = {
            "language": 100,  # Highest - language is critical
            "speech_pace": 90,
            "correction_style": 70,
        }
        return priorities.get(rule_type, 50)

    def _persist_rule(self, rule: ActiveRule):
        """Persist a rule to the database."""
        try:
            if rule.rule_id:
                # Update existing
                db_rule = self.db.get(TutorRule, rule.rule_id)
                if db_rule:
                    db_rule.description = rule.content
                    db_rule.priority = rule.priority
                    db_rule.updated_at = datetime.utcnow()
                    self.db.add(db_rule)
            else:
                # Check if similar rule exists (to avoid duplicates)
                existing = self.db.exec(
                    select(TutorRule)
                    .where(TutorRule.scope == "student")
                    .where(TutorRule.applies_to_student_id == self.user_id)
                    .where(TutorRule.type == rule.type)
                    .where(TutorRule.is_active == True)
                ).first()

                if existing:
                    # Update existing instead of creating new
                    existing.description = rule.content
                    existing.priority = rule.priority
                    existing.updated_at = datetime.utcnow()
                    self.db.add(existing)
                    rule.rule_id = existing.id
                else:
                    # Create new
                    db_rule = TutorRule(
                        scope="student",
                        type=rule.type,
                        title=f"{rule.type.replace('_', ' ').title()} Preference",
                        description=rule.content,
                        priority=rule.priority,
                        is_active=True,
                        applies_to_student_id=self.user_id,
                        created_by="system",
                        updated_by="system",
                        source="voice_detection",
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow(),
                    )
                    self.db.add(db_rule)
                    self.db.flush()
                    rule.rule_id = db_rule.id

            self.db.commit()
            logger.info(f"💾 Persisted rule: {rule.type} (id={rule.rule_id}) for user {self.user_id}")

        except Exception as e:
            logger.error(f"Failed to persist rule: {e}")
            self.db.rollback()

    def _format_rule_injection(self, rule: ActiveRule, is_new: bool = False) -> str:
        """Format a rule as a system message injection."""
        prefix = "🚨 NEW INSTRUCTION FROM STUDENT" if is_new else "📌 REMINDER"

        acknowledgment = ""
        if is_new:
            if rule.type == "language":
                if rule.value == "RU_ONLY":
                    acknowledgment = (
                        "\n\n⚠️ CRITICAL: You MUST acknowledge this IMMEDIATELY by saying: "
                        "'Хорошо, буду говорить по-русски.' or similar in RUSSIAN. "
                        "Then CONTINUE in Russian."
                    )
                else:
                    acknowledgment = (
                        "\n\n⚠️ CRITICAL: You MUST acknowledge this IMMEDIATELY by saying: "
                        "'Okay, I'll speak English now.' or similar in ENGLISH. "
                        "Then CONTINUE in English."
                    )
            elif rule.type == "speech_pace":
                acknowledgment = (
                    "\n\n⚠️ You MUST acknowledge by saying: "
                    "'Хорошо, буду говорить медленнее.' / 'Okay, I'll speak more slowly.' "
                    "Then demonstrate the slower pace immediately."
                )

        return f"{prefix}:\n{rule.content}{acknowledgment}"

    def _should_send_reminder(self) -> bool:
        """Check if we should send a rule reminder."""
        if not self.active_rules:
            return False

        # Only remind for high-priority rules
        high_priority_rules = [r for r in self.active_rules if r.priority >= 80]
        if not high_priority_rules:
            return False

        turns_since_reminder = self.turn_count - self.last_reminder_turn
        return turns_since_reminder >= self.reminder_interval

    def _build_reminder(self) -> Optional[str]:
        """Build a reminder message with active rules."""
        high_priority_rules = [r for r in self.active_rules if r.priority >= 80]
        if not high_priority_rules:
            return None

        self.last_reminder_turn = self.turn_count

        # Sort by priority
        sorted_rules = sorted(high_priority_rules, key=lambda r: r.priority, reverse=True)

        parts = ["📌 REMINDER - These rules are ACTIVE for this student:"]
        for rule in sorted_rules[:3]:  # Max 3 rules in reminder
            # Shorter version for reminders
            short_content = rule.content.split('.')[0] + '.'
            parts.append(f"• {short_content}")
            rule.reminder_count += 1

        parts.append("\n⚠️ You MUST continue following these rules.")

        return "\n".join(parts)

    def get_initial_rules_injection(self) -> Optional[str]:
        """
        Get all active rules as a single injection for session start.

        Call this at the beginning of a session to inject all persistent rules.
        """
        if not self.active_rules:
            return None

        sorted_rules = sorted(self.active_rules, key=lambda r: r.priority, reverse=True)

        parts = ["📌 STUDENT-SPECIFIC RULES (you MUST follow these strictly):"]
        for rule in sorted_rules:
            parts.append(f"• [{rule.type.upper()}] {rule.content}")
            rule.injected = True

        parts.append("\n⚠️ These rules were set by the student. Do NOT violate them.")

        return "\n".join(parts)

    def get_language_mode(self) -> Optional[str]:
        """Get the current language mode if a language rule is active."""
        for rule in self.active_rules:
            if rule.type == "language" and rule.value:
                return rule.value
        return None

    def force_reminder(self) -> Optional[str]:
        """Force a reminder now, regardless of turn count."""
        self.last_reminder_turn = 0  # Reset counter
        return self._build_reminder()

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about rule usage in this session."""
        return {
            "turn_count": self.turn_count,
            "active_rules_count": len(self.active_rules),
            "commands_detected": len(self.commands_this_session),
            "reminders_sent": sum(r.reminder_count for r in self.active_rules),
            "high_priority_rules": [
                {"type": r.type, "value": r.value}
                for r in self.active_rules if r.priority >= 80
            ],
        }
