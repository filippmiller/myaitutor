from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel
from typing import List, Optional, Any
import json

from sqlmodel import Session

from app.database import get_session
from app.models import AppSettings, UserAccount, TutorRule, TutorRuleVersion, RuleGenerationLog
from app.services.auth_service import get_current_user
from app.services.voice_engine import OpenAIVoiceEngine


router = APIRouter()


class RuleDraft(BaseModel):
    scope: str
    type: str
    title: str
    description: str
    trigger_condition: Optional[Any] = None
    action: Optional[Any] = None
    priority: int = 0


class VoiceRulesDraftResponse(BaseModel):
    transcript: str
    rules: List[RuleDraft]
    generation_log_id: Optional[int] = None


class SaveVoiceRulesRequest(BaseModel):
    rules: List[RuleDraft]
    generation_log_id: Optional[int] = None


class ChunkTranscriptionResponse(BaseModel):
    text: str


class GenerateFromTextRequest(BaseModel):
    transcript: str


class HealthResponse(BaseModel):
    openai_key_set: bool


def _get_settings_or_400(session: Session) -> AppSettings:
    settings = session.get(AppSettings, 1)
    if not settings or not settings.openai_api_key:
        raise HTTPException(status_code=400, detail="OpenAI API key not configured in admin settings")
    return settings


def _generate_rule_drafts_from_transcript(
    transcript: str,
    current_user: UserAccount,
    session: Session,
    settings: AppSettings,
) -> VoiceRulesDraftResponse:
    """Internal helper: call Chat Completion and return draft rules + log id."""
    from openai import OpenAI

    client = OpenAI(api_key=settings.openai_api_key)

    system_prompt = (
        "You are an assistant that converts an admin's natural language description of "
        "tutor behavior into a JSON list of structured rules. The admin speaks in Russian, "
        "but you must output JSON in English field names. Each rule controls how the AIlingva "
        "English tutor behaves during voice lessons. Rules will be saved into a TutorRule table.\n\n"
        "Return ONLY a JSON object with a top-level 'rules' array and no extra text."
    )

    schema_description = (
        "Each rule MUST have: scope, type, title, description, trigger_condition, action, priority.\n"
        "- scope: one of 'global', 'student', 'session', 'app'. Use 'global' by default unless the admin explicitly "
        "talks about a specific student or a single session.\n"
        "- type: one of 'greeting', 'language_mode', 'tone', 'age_logic', 'lesson_number_logic', 'other'.\n"
        "- title: short human readable summary (in Russian is OK).\n"
        "- description: longer explanation (1-3 sentences, Russian is OK).\n"
        "- trigger_condition: JSON object describing WHEN the rule applies. Support nested logic using 'all'/'any'.\n"
        "  Example: {""all"": [{""field"": ""lesson_number"", ""op"": ""in"", ""value"": [2,3]}, {""field"": ""phase"", ""op"": ""=="", ""value"": ""lesson_start""}]}.\n"
        "- action: JSON describing WHAT the tutor does or says. Include fields like 'speak_variants' (array of example "
        "phrases in Russian), 'tone' (e.g. 'playful', 'formal', 'youth_slang'), and any other useful flags.\n"
        "- priority: integer, where lower numbers are applied first. Use 0 as default, or smaller numbers for very important rules.\n\n"
        "If the admin describes multiple scenarios, output multiple rules in the 'rules' array."
    )

    user_prompt = (
        "Admin's spoken description of rules (in Russian). Convert it to rules as per schema.\n\n"
        f"TRANSCRIPT:\n{transcript}\n\n"
        "Respond with a single JSON object like: {\"rules\": [ ... ]}."
    )

    try:
        completion = client.chat.completions.create(
            model=settings.default_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "system", "content": schema_description},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OpenAI rule generation failed: {e}")

    content = completion.choices[0].message.content

    # Parse JSON and build RuleDrafts
    try:
        parsed = json.loads(content or "{}")
        raw_rules = parsed.get("rules") or []
    except Exception as e:
        # Save raw response for debugging
        log = RuleGenerationLog(
            admin_user_id=current_user.id,
            input_transcript=transcript,
            raw_model_response=content,
        )
        session.add(log)
        session.commit()
        raise HTTPException(status_code=500, detail=f"Failed to parse OpenAI JSON: {e}")

    # Create log row now that JSON parsed successfully
    log = RuleGenerationLog(
        admin_user_id=current_user.id,
        input_transcript=transcript,
        raw_model_response=content,
    )
    session.add(log)
    session.commit()
    session.refresh(log)

    drafts: List[RuleDraft] = []
    for r in raw_rules:
        try:
            drafts.append(RuleDraft(**r))
        except Exception:
            # Skip malformed rule entries, but keep others
            continue

    return VoiceRulesDraftResponse(
        transcript=transcript,
        rules=drafts,
        generation_log_id=log.id,
    )


@router.get("/health", response_model=HealthResponse)
def voice_rules_health(
    current_user: UserAccount = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Quick health check so frontend can fail fast before recording."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")

    settings = session.get(AppSettings, 1)
    return HealthResponse(openai_key_set=bool(settings and settings.openai_api_key))


@router.post("/transcribe-and-draft", response_model=VoiceRulesDraftResponse)
async def transcribe_and_draft_rules(
    audio_file: UploadFile = File(...),
    current_user: UserAccount = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Admin-only endpoint to turn a spoken description into draft tutor rules.

    1. Transcribes the uploaded audio using OpenAI Whisper.
    2. Sends the transcript to Chat Completion with a strict JSON schema.
    3. Returns the transcript and the structured rule drafts (NOT yet saved).
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")

    settings = _get_settings_or_400(session)

    # Read audio bytes
    audio_bytes = await audio_file.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio file")

    # 1. STT via existing OpenAIVoiceEngine helper
    try:
        stt_engine = OpenAIVoiceEngine(api_key=settings.openai_api_key)
        transcript = await stt_engine.transcribe(audio_bytes)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"STT failed: {e}")

    # 2. Use Chat Completion to turn transcript into structured rule drafts
    return _generate_rule_drafts_from_transcript(
        transcript=transcript,
        current_user=current_user,
        session=session,
        settings=settings,
    )


@router.post("/transcribe-chunk", response_model=ChunkTranscriptionResponse)
async def transcribe_chunk(
    audio_file: UploadFile = File(...),
    current_user: UserAccount = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Transcribe a short audio chunk for realtime-ish transcript preview in the UI."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")

    settings = _get_settings_or_400(session)

    audio_bytes = await audio_file.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio file")

    try:
        stt_engine = OpenAIVoiceEngine(api_key=settings.openai_api_key)
        text = await stt_engine.transcribe(audio_bytes)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"STT failed: {e}")

    return ChunkTranscriptionResponse(text=text)


@router.post("/generate-from-text", response_model=VoiceRulesDraftResponse)
async def generate_from_text(
    data: GenerateFromTextRequest,
    current_user: UserAccount = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Generate draft rules directly from a transcript string.

    Used by the frontend when it has already built a transcript via streaming
    chunk transcription and only needs rule generation once at the end.
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")

    if not data.transcript.strip():
        raise HTTPException(status_code=400, detail="Transcript is empty")

    settings = _get_settings_or_400(session)
    return _generate_rule_drafts_from_transcript(
        transcript=data.transcript,
        current_user=current_user,
        session=session,
        settings=settings,
    )


@router.post("/save")
async def save_voice_rules(
    data: SaveVoiceRulesRequest,
    current_user: UserAccount = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """Persist selected voice-generated rules as TutorRule rows.

    The incoming rules are already structured. We JSON-encode trigger_condition and
    action, create TutorRule + TutorRuleVersion entries, and optionally link back
    to a RuleGenerationLog.
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")

    if not data.rules:
        return {"saved_rules": []}

    saved_rules: List[TutorRule] = []
    saved_ids: List[int] = []

    for rule_draft in data.rules:
        # Basic validation
        if not rule_draft.scope or not rule_draft.type or not rule_draft.title or not rule_draft.description:
            continue

        trigger_json = (
            json.dumps(rule_draft.trigger_condition, ensure_ascii=False)
            if rule_draft.trigger_condition is not None
            else None
        )
        action_json = (
            json.dumps(rule_draft.action, ensure_ascii=False)
            if rule_draft.action is not None
            else None
        )

        rule = TutorRule(
            scope=rule_draft.scope,
            type=rule_draft.type,
            title=rule_draft.title,
            description=rule_draft.description,
            trigger_condition=trigger_json,
            action=action_json,
            priority=rule_draft.priority or 0,
            is_active=True,
            created_by="human_admin",
            updated_by="human_admin",
            source="voice_admin",
        )
        session.add(rule)
        session.commit()
        session.refresh(rule)

        version = TutorRuleVersion(
            rule_id=rule.id,
            scope=rule.scope,
            type=rule.type,
            title=rule.title,
            description=rule.description,
            trigger_condition=rule.trigger_condition,
            action=rule.action,
            priority=rule.priority,
            is_active=rule.is_active,
            changed_by="human_admin",
            change_reason="Created via voice rule builder",
        )
        session.add(version)
        session.commit()

        saved_rules.append(rule)
        saved_ids.append(rule.id)

    # Optionally link back to generation log
    if data.generation_log_id:
        log = session.get(RuleGenerationLog, data.generation_log_id)
        if log and log.admin_user_id == current_user.id:
            log.saved_rule_ids_json = json.dumps(saved_ids)
            session.add(log)
            session.commit()

    return {"saved_rules": saved_rules}
