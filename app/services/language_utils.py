# Helper function to parse language mode markers from AI responses
import re
from typing import Optional, Tuple

def parse_language_mode_marker(text: str) -> Optional[Tuple[str, Optional[int]]]:
    """
    Parse language mode markers from AI response text.
    
    Returns: (language_mode, language_level) or None
    
    Examples:
        "[LANGUAGE_MODE_DETECTED: EN_ONLY]" -> ("EN_ONLY", None)
        "[LANGUAGE_MODE_DETECTED: MIXED]" -> ("MIXED", None)  
        "[LANGUAGE_LEVEL_UP]" -> (None, +1) # Indicates level should increment
    """
    # Detect initial mode selection
    mode_match = re.search(r'\[LANGUAGE_MODE_DETECTED:\s*(\w+)\]', text)
    if mode_match:
        mode = mode_match.group(1).upper()
        if mode in ["EN_ONLY", "RU_ONLY", "MIXED"]:
            return (mode, None)
    
    # Detect level up request
    if "[LANGUAGE_LEVEL_UP]" in text:
        return (None, "LEVEL_UP")
    
    return None

def strip_language_markers(text: str) -> str:
    """Remove language mode markers from text before displaying to user."""
    text = re.sub(r'\[LANGUAGE_MODE:\s*\w+\]', '', text)
    text = re.sub(r'\[LANGUAGE_MODE_DETECTED:\s*\w+\]', '', text)
    text = re.sub(r'\[LANGUAGE_LEVEL_UP\]', '', text)
    return text.strip()
