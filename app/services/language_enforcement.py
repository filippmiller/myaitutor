"""
Language Enforcement Service for AIlingva

This service ensures the tutor speaks in the correct language based on the
selected language mode. It validates responses and can trigger regeneration
if the model speaks in the wrong language.

Language Modes:
- EN_ONLY: 95%+ English, Russian only for critical clarifications
- RU_ONLY: Mostly Russian, English as learning material only
- MIXED: Adaptive balance based on student comfort
"""

import re
import logging
from typing import Optional, Tuple, Literal
from enum import Enum

logger = logging.getLogger(__name__)


class LanguageMode(str, Enum):
    EN_ONLY = "EN_ONLY"
    RU_ONLY = "RU_ONLY"
    MIXED = "MIXED"


# Common words/patterns for language detection
RUSSIAN_PATTERNS = [
    r'[а-яёА-ЯЁ]{3,}',  # 3+ Cyrillic characters
]

ENGLISH_PATTERNS = [
    r'\b(the|is|are|was|were|have|has|had|will|would|could|should|can|do|does|did)\b',
    r'\b(I|you|he|she|it|we|they)\b',
    r'\b(and|or|but|because|if|when|where|what|how|why)\b',
]

# FORBIDDEN languages - we should NEVER speak these
FORBIDDEN_LANGUAGE_PATTERNS = {
    'spanish': [
        r'\b(hola|gracias|por favor|buenos días|buenas|qué|cómo|está|estás|usted)\b',
        r'\b(tengo|tiene|quiero|puedo|vamos|muy|también|pero|porque|cuando)\b',
    ],
    'french': [
        r'\b(bonjour|merci|s\'il vous plaît|comment|êtes|avez|voulez|pouvez)\b',
        r'\b(je suis|tu es|il est|nous sommes|très|aussi|mais|parce que)\b',
    ],
    'german': [
        r'\b(guten tag|danke|bitte|wie geht|haben|können|möchten|wollen)\b',
        r'\b(ich bin|du bist|er ist|wir sind|sehr|auch|aber|weil|wenn)\b',
    ],
    'italian': [
        r'\b(ciao|grazie|prego|come stai|buongiorno|buonasera)\b',
        r'\b(sono|sei|siamo|hanno|voglio|posso|molto|anche|ma|perché)\b',
    ],
    'portuguese': [
        r'\b(olá|obrigado|por favor|como vai|bom dia|boa tarde)\b',
        r'\b(eu sou|você é|nós somos|tenho|quero|posso|muito|também|mas)\b',
    ],
}


def detect_language_ratio(text: str) -> Tuple[float, float]:
    """
    Detect the ratio of Russian vs English content in text.

    Returns:
        Tuple of (russian_ratio, english_ratio) where each is 0.0-1.0
    """
    if not text or len(text.strip()) < 5:
        return 0.0, 0.0

    # Count Russian characters
    russian_chars = len(re.findall(r'[а-яёА-ЯЁ]', text))

    # Count English characters
    english_chars = len(re.findall(r'[a-zA-Z]', text))

    total_chars = russian_chars + english_chars
    if total_chars == 0:
        return 0.0, 0.0

    russian_ratio = russian_chars / total_chars
    english_ratio = english_chars / total_chars

    return russian_ratio, english_ratio


def detect_forbidden_language(text: str) -> Optional[str]:
    """
    Check if text contains forbidden languages (Spanish, French, German, etc.)

    Returns:
        Name of forbidden language detected, or None if clean
    """
    text_lower = text.lower()

    for lang_name, patterns in FORBIDDEN_LANGUAGE_PATTERNS.items():
        matches = 0
        for pattern in patterns:
            if re.search(pattern, text_lower, re.IGNORECASE):
                matches += 1

        # If 2+ patterns match, it's likely this language
        if matches >= 2:
            logger.warning(f"Forbidden language detected: {lang_name} (matches: {matches})")
            return lang_name

    return None


def validate_language_mode(
    text: str,
    mode: Optional[str],
    strict: bool = True
) -> Tuple[bool, str, Optional[str]]:
    """
    Validate that the tutor response matches the expected language mode.

    Args:
        text: The tutor's response text
        mode: The language mode (EN_ONLY, RU_ONLY, MIXED, or None)
        strict: If True, apply stricter validation

    Returns:
        Tuple of (is_valid, reason, suggested_action)
        - is_valid: True if response is acceptable
        - reason: Explanation of the validation result
        - suggested_action: "regenerate", "warn", or None
    """
    if not text or len(text.strip()) < 10:
        return True, "Text too short to validate", None

    # First, check for forbidden languages (always invalid)
    forbidden = detect_forbidden_language(text)
    if forbidden:
        return False, f"Response contains {forbidden} - must use English/Russian only", "regenerate"

    russian_ratio, english_ratio = detect_language_ratio(text)

    logger.debug(f"Language ratio - Russian: {russian_ratio:.2%}, English: {english_ratio:.2%}")

    # If mode not set yet, any English/Russian mix is acceptable
    if not mode:
        if russian_ratio + english_ratio > 0.5:
            return True, "No mode set, English/Russian content detected", None
        return True, "No mode set, cannot validate", None

    mode = mode.upper()

    if mode == "EN_ONLY":
        # Should be 80%+ English (allowing some Russian for names, clarifications)
        if english_ratio < 0.7:
            if strict:
                return False, f"EN_ONLY mode but only {english_ratio:.0%} English", "regenerate"
            return False, f"EN_ONLY mode but only {english_ratio:.0%} English", "warn"
        return True, f"EN_ONLY mode validated ({english_ratio:.0%} English)", None

    elif mode == "RU_ONLY":
        # Should be 60%+ Russian (allowing English words being taught)
        if russian_ratio < 0.4:
            if strict:
                return False, f"RU_ONLY mode but only {russian_ratio:.0%} Russian", "regenerate"
            return False, f"RU_ONLY mode but only {russian_ratio:.0%} Russian", "warn"
        return True, f"RU_ONLY mode validated ({russian_ratio:.0%} Russian)", None

    elif mode == "MIXED":
        # Any ratio is acceptable in mixed mode, as long as it's English/Russian
        total_valid = russian_ratio + english_ratio
        if total_valid < 0.5:
            return False, "MIXED mode but content is neither English nor Russian", "warn"
        return True, f"MIXED mode validated (RU: {russian_ratio:.0%}, EN: {english_ratio:.0%})", None

    return True, f"Unknown mode '{mode}', skipping validation", None


def get_language_enforcement_prompt(mode: Optional[str]) -> str:
    """
    Get a SHORT, STRICT language enforcement instruction to inject into prompts.

    This returns a compact instruction that can be prepended to the system prompt
    to reinforce language constraints.
    """
    if not mode:
        return """
LANGUAGE: Start in Russian to greet, then detect student's language preference.
FORBIDDEN: Never speak Spanish, French, German, Italian, or Portuguese.
"""

    mode = mode.upper()

    if mode == "EN_ONLY":
        return """
🚨 STRICT LANGUAGE MODE: ENGLISH ONLY
- Speak 95% English
- Russian ONLY if student is completely stuck (1-2 words max)
- NEVER use Spanish, French, German, Italian, Portuguese
- If you catch yourself using another language, STOP and switch to English
"""

    elif mode == "RU_ONLY":
        return """
🚨 STRICT LANGUAGE MODE: RUSSIAN ONLY
- Speak Russian for all explanations and conversation
- English ONLY for teaching new words/phrases (with Russian translations)
- NEVER use Spanish, French, German, Italian, Portuguese
- Format: "Новое слово: 'apple' - это 'яблоко'"
"""

    elif mode == "MIXED":
        return """
🚨 LANGUAGE MODE: MIXED (Russian + English)
- Balance Russian explanations with English practice
- Start with more Russian, gradually increase English
- NEVER use Spanish, French, German, Italian, Portuguese
- Adapt to student comfort level
"""

    return ""


def clean_response_language(text: str, mode: Optional[str]) -> str:
    """
    Attempt to clean a response by removing obvious forbidden language fragments.

    This is a last-resort fix; prefer regeneration for serious violations.
    """
    if not text:
        return text

    # Remove common Spanish/French/German greetings that might slip in
    replacements = [
        (r'\b[Hh]ola\b', 'Hello'),
        (r'\b[Bb]onjour\b', 'Hello'),
        (r'\b[Gg]uten [Tt]ag\b', 'Hello'),
        (r'\b[Cc]iao\b', 'Hi'),
        (r'\b[Gg]racias\b', 'Thank you'),
        (r'\b[Mm]erci\b', 'Thank you'),
        (r'\b[Dd]anke\b', 'Thank you'),
    ]

    cleaned = text
    for pattern, replacement in replacements:
        cleaned = re.sub(pattern, replacement, cleaned)

    if cleaned != text:
        logger.info(f"Cleaned forbidden language from response")

    return cleaned


class LanguageEnforcer:
    """
    Stateful language enforcer that tracks violations and can escalate actions.
    """

    def __init__(self, mode: Optional[str] = None):
        self.mode = mode
        self.violation_count = 0
        self.last_violation_reason: Optional[str] = None

    def set_mode(self, mode: str):
        """Update the language mode."""
        self.mode = mode
        logger.info(f"Language mode set to: {mode}")

    def validate(self, text: str) -> Tuple[bool, str, Optional[str]]:
        """
        Validate text and track violations.

        Returns same as validate_language_mode().
        """
        is_valid, reason, action = validate_language_mode(
            text,
            self.mode,
            strict=(self.violation_count < 2)  # Less strict after repeated violations
        )

        if not is_valid:
            self.violation_count += 1
            self.last_violation_reason = reason
            logger.warning(f"Language violation #{self.violation_count}: {reason}")

        return is_valid, reason, action

    def get_enforcement_prompt(self) -> str:
        """Get the enforcement prompt, possibly strengthened after violations."""
        base_prompt = get_language_enforcement_prompt(self.mode)

        if self.violation_count > 0:
            base_prompt += f"\n⚠️ WARNING: {self.violation_count} language violation(s) detected. BE STRICT."

        if self.violation_count >= 3:
            base_prompt += "\n🚨 CRITICAL: Multiple violations. Use ONLY English and Russian. NO OTHER LANGUAGES."

        return base_prompt

    def reset_violations(self):
        """Reset violation counter (e.g., after mode change)."""
        self.violation_count = 0
        self.last_violation_reason = None
