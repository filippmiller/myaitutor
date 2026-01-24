"""
Student-friendly error messages for critical system failures.

These messages are designed to be shown to students when the lesson cannot continue
due to technical issues (API errors, quota exceeded, etc.).
"""

# Critical error types that should trigger student-friendly messages
CRITICAL_ERROR_PATTERNS = [
    "insufficient_quota",
    "rate_limit",
    "invalid_api_key",
    "authentication",
    "billing",
    "exceeded your current quota",
    "api key",
    "unauthorized",
    "forbidden",
    "service unavailable",
    "internal server error",
    "connection refused",
    "timeout",
]


def is_critical_api_error(error_message: str) -> bool:
    """Check if an error message indicates a critical API failure."""
    if not error_message:
        return False
    lower_msg = error_message.lower()
    return any(pattern in lower_msg for pattern in CRITICAL_ERROR_PATTERNS)


# Student-facing messages (English)
STUDENT_ERROR_MESSAGES = {
    "service_unavailable": (
        "We're sorry, but the class cannot take place right now due to technical difficulties. "
        "Please contact the administrator to check for technical problems."
    ),
    "api_key_missing": (
        "The lesson service is not properly configured. "
        "Please contact the administrator to resolve this issue."
    ),
    "all_fallbacks_failed": (
        "We're experiencing technical difficulties with all available services. "
        "Please contact the administrator and try again later."
    ),
    "connection_lost": (
        "The connection to the lesson service was lost. "
        "Please refresh the page to reconnect, or contact the administrator if the problem persists."
    ),
}

# Russian translations for future use
STUDENT_ERROR_MESSAGES_RU = {
    "service_unavailable": (
        "К сожалению, урок не может состояться из-за технических неполадок. "
        "Пожалуйста, свяжитесь с администратором для проверки технических проблем."
    ),
    "api_key_missing": (
        "Сервис уроков не настроен должным образом. "
        "Пожалуйста, свяжитесь с администратором для решения этой проблемы."
    ),
    "all_fallbacks_failed": (
        "Все доступные сервисы испытывают технические трудности. "
        "Пожалуйста, свяжитесь с администратором и попробуйте позже."
    ),
    "connection_lost": (
        "Соединение с сервисом уроков было потеряно. "
        "Пожалуйста, обновите страницу для переподключения или свяжитесь с администратором."
    ),
}


def get_student_error_message(error_key: str, lang: str = "en") -> str:
    """Get a student-friendly error message by key and language."""
    messages = STUDENT_ERROR_MESSAGES_RU if lang == "ru" else STUDENT_ERROR_MESSAGES
    return messages.get(error_key, messages["service_unavailable"])


def classify_api_error(error_message: str) -> str:
    """Classify an API error into a student-friendly error key."""
    if not error_message:
        return "service_unavailable"

    lower_msg = error_message.lower()

    if "api key" in lower_msg or "unauthorized" in lower_msg or "authentication" in lower_msg:
        return "api_key_missing"

    if "quota" in lower_msg or "billing" in lower_msg or "rate_limit" in lower_msg:
        return "service_unavailable"

    if "timeout" in lower_msg or "connection" in lower_msg:
        return "connection_lost"

    return "service_unavailable"
