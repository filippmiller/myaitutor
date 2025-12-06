from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from app.database import get_session
from app.models import AppSettings, UserAccount, UserProfile, TutorSystemRule, DebugSettings
from app.services.auth_service import get_current_user
from pydantic import BaseModel
import openai
import requests

import os
import json
from datetime import datetime
from glob import glob

router = APIRouter()

class SettingsUpdate(BaseModel):
    openai_api_key: str
    default_model: str


class DebugSettingsUpdate(BaseModel):
    voice_logging_enabled: bool


@router.get("/settings")
def get_settings(session: Session = Depends(get_session)):
    settings = session.get(AppSettings, 1)
    if not settings:
        return {
            "openai_api_key": None, 
            "default_model": "gpt-4o-mini"
        }
    return settings

@router.post("/settings")
def update_settings(data: SettingsUpdate, session: Session = Depends(get_session)):
    settings = session.get(AppSettings, 1)
    if not settings:
        settings = AppSettings(id=1)
    
    settings.openai_api_key = data.openai_api_key
    settings.default_model = data.default_model
    
    session.add(settings)
    session.commit()
    session.refresh(settings)
    return settings

@router.get("/debug-settings")
def get_debug_settings(session: Session = Depends(get_session)):
    settings = session.get(DebugSettings, 1)
    if not settings:
        return {"voice_logging_enabled": False}
    return settings

@router.post("/debug-settings")
def update_debug_settings(data: DebugSettingsUpdate, session: Session = Depends(get_session)):
    settings = session.get(DebugSettings, 1)
    if not settings:
        settings = DebugSettings(id=1)
    settings.voice_logging_enabled = data.voice_logging_enabled
    session.add(settings)
    session.commit()
    session.refresh(settings)
    return settings

@router.post("/test-openai")
def test_openai(session: Session = Depends(get_session)):
    settings = session.get(AppSettings, 1)
    if not settings or not settings.openai_api_key:
        raise HTTPException(status_code=400, detail="OpenAI API Key not set")
    
    try:
        client = openai.OpenAI(api_key=settings.openai_api_key)
        response = client.chat.completions.create(
            model=settings.default_model,
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=5
        )
        return {"status": "ok", "message": "OpenAI connection successful", "response": response.choices[0].message.content}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@router.post("/test-ffmpeg")
def test_ffmpeg(session: Session = Depends(get_session)):
    import shutil
    import subprocess
    
    ffmpeg_path = shutil.which("ffmpeg")
    if not ffmpeg_path:
        return {"status": "error", "message": "ffmpeg not found in PATH"}
        
    try:
        result = subprocess.run([ffmpeg_path, "-version"], capture_output=True, text=True)
        return {"status": "ok", "message": f"ffmpeg found: {result.stdout.splitlines()[0]}"}
    except Exception as e:
        return {"status": "error", "message": f"ffmpeg execution failed: {str(e)}"}

@router.get("/users")
def list_users(
    offset: int = 0, 
    limit: int = 50, 
    current_user: UserAccount = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    
    users = session.exec(select(UserAccount).offset(offset).limit(limit)).all()
    return users

@router.get("/users/{user_id}")
def get_user_details(
    user_id: int,
    current_user: UserAccount = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
        
    user = session.get(UserAccount, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    # Get profile
    profile = session.exec(select(UserProfile).where(UserProfile.user_account_id == user.id)).first()
    
    return {
        "account": user,
        "profile": profile
    }

class UserPreferencesUpdate(BaseModel):
    preferred_address: str | None = None
    preferred_voice: str | None = None

@router.patch("/users/{user_id}/preferences")
def update_user_preferences(
    user_id: int,
    data: UserPreferencesUpdate,
    current_user: UserAccount = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
        
    user = session.get(UserAccount, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    profile = session.exec(select(UserProfile).where(UserProfile.user_account_id == user.id)).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
        
    import json
    try:
        prefs = json.loads(profile.preferences)
    except:
        prefs = {}
        
    if data.preferred_address is not None:
        prefs["preferred_address"] = data.preferred_address
    if data.preferred_voice is not None:
        prefs["preferred_voice"] = data.preferred_voice
        
    profile.preferences = json.dumps(prefs)
    session.add(profile)
    session.commit()
    session.refresh(profile)
    
    return profile

class TestVoiceRequest(BaseModel):
    text: str
    voice: str

@router.post("/test-voice-gen")
async def test_voice_gen(
    data: TestVoiceRequest,
    current_user: UserAccount = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
        
    settings = session.get(AppSettings, 1)
    
    # 1. Check Yandex
    yandex_voices = ['alisa', 'alena', 'filipp', 'jane', 'madirus', 'omazh', 'zahar', 'ermil']
    
    import os
    import uuid
    from fastapi.responses import FileResponse
    
    temp_filename = f"static/audio/test_{uuid.uuid4()}.mp3"
    os.makedirs("static/audio", exist_ok=True)
    full_path = os.path.join(os.getcwd(), temp_filename)
    
    if data.voice in yandex_voices:
        try:
            from app.services.yandex_service import YandexService
            import subprocess
            yandex_service = YandexService()
            
            process = subprocess.Popen(
                [
                    "ffmpeg",
                    "-f", "s16le", "-ar", "48000", "-ac", "1", "-i", "pipe:0",
                    "-y",
                    full_path
                ],
                stdin=subprocess.PIPE,
                stderr=subprocess.DEVNULL
            )
            
            for chunk in yandex_service.synthesize_stream(text=data.text, voice=data.voice):
                try:
                    process.stdin.write(chunk)
                except BrokenPipeError:
                    break
            
            process.stdin.close()
            process.wait()
            
            return FileResponse(full_path)
        except Exception as e:
            print(f"Yandex Test Failed: {e}")
            raise HTTPException(status_code=500, detail=f"Yandex TTS failed: {str(e)}")
            
    # 2. Fallback to OpenAI
    if not settings or not settings.openai_api_key:
        raise HTTPException(status_code=400, detail="OpenAI key not configured")

    try:
        client = openai.OpenAI(api_key=settings.openai_api_key)
        response = client.audio.speech.create(
            model="tts-1",
            voice=data.voice if data.voice in ["alloy", "echo", "fable", "onyx", "nova", "shimmer"] else "alloy",
            input=data.text
        )
        response.stream_to_file(full_path)
        return FileResponse(full_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OpenAI TTS failed: {str(e)}")

@router.get("/system-rules")
def list_system_rules(
    current_user: UserAccount = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
        
    rules = session.exec(select(TutorSystemRule).order_by(TutorSystemRule.sort_order)).all()
    return rules

class SystemRuleUpdate(BaseModel):
    rule_text: str
    enabled: bool
    sort_order: int

@router.patch("/system-rules/{rule_id}")
def update_system_rule(
    rule_id: int,
    data: SystemRuleUpdate,
    current_user: UserAccount = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
        
    rule = session.get(TutorSystemRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
        
    rule.rule_text = data.rule_text
    rule.enabled = data.enabled
    rule.sort_order = data.sort_order
    
    session.add(rule)
    session.commit()
    session.refresh(rule)
    return rule

# Voice Management Endpoints

@router.get("/voices")
def list_voices():
    return {
        "openai": [
            {"id": "alloy", "name": "Alloy", "gender": "neutral"},
            {"id": "echo", "name": "Echo", "gender": "male"},
            {"id": "fable", "name": "Fable", "gender": "neutral"},
            {"id": "onyx", "name": "Onyx", "gender": "male"},
            {"id": "nova", "name": "Nova", "gender": "female"},
            {"id": "shimmer", "name": "Shimmer", "gender": "female"},
        ],
        "yandex": [
            {"id": "alisa", "name": "Alisa", "gender": "female"},
            {"id": "alena", "name": "Alena", "gender": "female"},
            {"id": "filipp", "name": "Filipp", "gender": "male"},
            {"id": "jane", "name": "Jane", "gender": "female"},
            {"id": "madirus", "name": "Madirus", "gender": "male"},
            {"id": "omazh", "name": "Omazh", "gender": "female"},
            {"id": "zahar", "name": "Zahar", "gender": "male"},
            {"id": "ermil", "name": "Ermil", "gender": "male"},
        ]
    }

class VoiceTestRequest(BaseModel):
    engine: str
    voice_id: str
    text: str = "Hello, this is a test of the selected voice."

@router.post("/voices/test")
async def test_voice_new(
    data: VoiceTestRequest,
    current_user: UserAccount = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")

    settings = session.get(AppSettings, 1)
    api_key = settings.openai_api_key if settings else None
    
    from app.services.voice_engine import get_voice_engine
    import uuid
    import os
    from fastapi.responses import FileResponse
    
    try:
        engine = get_voice_engine(data.engine, api_key=api_key)
        audio_bytes = await engine.synthesize(data.text, voice_id=data.voice_id)
        
        # Save to temp file
        temp_filename = f"static/audio/test_{uuid.uuid4()}.mp3"
        os.makedirs("static/audio", exist_ok=True)
        full_path = os.path.join(os.getcwd(), temp_filename)
        
        with open(full_path, "wb") as f:
            f.write(audio_bytes)
            
        return FileResponse(full_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class UserVoiceSettings(BaseModel):
    preferred_tts_engine: str
    preferred_stt_engine: str
    preferred_voice_id: str

@router.post("/users/{user_id}/voice")
def save_user_voice(
    user_id: int,
    data: UserVoiceSettings,
    current_user: UserAccount = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
        
    user = session.get(UserAccount, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    profile = session.exec(select(UserProfile).where(UserProfile.user_account_id == user.id)).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
        
    try:
        profile.preferred_tts_engine = data.preferred_tts_engine
        profile.preferred_stt_engine = data.preferred_stt_engine
        profile.preferred_voice_id = data.preferred_voice_id
        
        # Sync with JSON preferences for backward compatibility/frontend ease if needed
        import json
        try:
            prefs = json.loads(profile.preferences)
        except:
            prefs = {}
        prefs["preferred_voice"] = data.preferred_voice_id # Legacy field
        profile.preferences = json.dumps(prefs)
        
        session.add(profile)
        session.commit()
        session.refresh(profile)
        
        return profile
    except Exception as e:
        print(f"Error saving voice settings: {e}")
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")


@router.get("/voice/stack")
def get_voice_stack(
    current_user: UserAccount = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
        
    settings = session.get(AppSettings, 1)
    
    # Get stats
    from app.api.voice_ws import get_latency_stats
    stats = get_latency_stats()
    
    return {
        "stt": {
            "provider": "openai-realtime" if not settings else "openai (whisper)", # Simplified view
            "model": "whisper-1",
            "streaming": True
        },
        "tts": {
            "provider": "openai/yandex",
            "model": "tts-1/yandex",
            "streaming": True
        },
        "latency": stats
    }

# --- Voice Stack / Latency ---

@router.get("/voice/stack")
def get_voice_stack(
    current_user: UserAccount = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
        
    settings = session.get(AppSettings, 1)
    
    # Get stats
    from app.api.voice_ws import get_latency_stats
    stats = get_latency_stats()
    
    return {
        "stt": {
            "provider": "openai-realtime" if not settings else "openai (whisper)", # Simplified view
            "model": "whisper-1",
            "streaming": True
        },
        "tts": {
            "provider": "openai/yandex",
            "model": "tts-1/yandex",
            "streaming": True
        },
        "latency": stats
    }

# --- Lesson Prompt Logs ---

@router.get("/lesson-prompts")
def list_lesson_prompts(
    limit: int = 50,
    user_id: int | None = None,
    current_user: UserAccount = Depends(get_current_user),
):
    """Return recent lesson prompt snapshots (system + greeting prompts).

    Logs are stored as JSON files in static/prompts and are intentionally kept
    outside the DB schema so we can iterate quickly on prompt engineering.
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")

    prompts_dir = os.path.join(os.getcwd(), "static", "prompts")
    if not os.path.exists(prompts_dir):
        return []

    items = []
    pattern = os.path.join(prompts_dir, "lesson_*_prompt.json")
    for path in glob(pattern):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Attach file-based timestamp if JSON doesn't have one
            if "created_at" not in data:
                ts = datetime.fromtimestamp(os.path.getmtime(path))
                data["created_at"] = ts.isoformat()
            # Filter by user_id if provided
            if user_id is not None and data.get("user_account_id") != user_id:
                continue
            items.append(data)
        except Exception as e:
            # Don't break the endpoint because of one bad file
            print(f"Failed to read lesson prompt log {path}: {e}")
            continue

    # Sort newest first
    items.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return items[:limit]


# --- Lesson OpenAI Traffic Logs ---

@router.get("/lesson-logs")
def get_lesson_logs(
    lesson_session_id: int | None = None,
    limit_lines: int = 500,
    current_user: UserAccount = Depends(get_current_user),
):
    """Return OpenAI traffic logs for a given lesson, or list available logs.

    Logs are stored as JSONL files in static/openai_logs/lesson_<id>.jsonl.
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")

    logs_dir = os.path.join(os.getcwd(), "static", "openai_logs")
    if not os.path.exists(logs_dir):
        return [] if lesson_session_id is None else {"lesson_session_id": lesson_session_id, "entries": []}

    # If no specific lesson requested, list available log files
    if lesson_session_id is None:
        files = []
        for path in glob(os.path.join(logs_dir, "lesson_*.jsonl")):
            try:
                name = os.path.basename(path)
                # lesson_<id>.jsonl
                parts = name.split("_")
                if len(parts) < 2:
                    continue
                id_part = parts[1].split(".")[0]
                les_id = int(id_part)
                ts = os.path.getmtime(path)
                files.append({
                    "lesson_session_id": les_id,
                    "path": name,
                    "updated_at": datetime.fromtimestamp(ts).isoformat(),
                })
            except Exception:
                continue
        # newest first
        files.sort(key=lambda x: x["lesson_session_id"], reverse=True)
        return files

    # Read specific lesson log
    file_path = os.path.join(logs_dir, f"lesson_{lesson_session_id}.jsonl")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Log file not found for this lesson")

    entries: list[dict] = []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        # take last N lines
        for line in lines[-limit_lines:]:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except Exception:
                continue
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read log file: {str(e)}")

    return {"lesson_session_id": lesson_session_id, "entries": entries}


# --- Beginner Rules Management ---

@router.get("/beginner-rules")
def get_beginner_rules(
    current_user: UserAccount = Depends(get_current_user)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    
    import os
    import json
    rules_path = os.path.join(os.getcwd(), "app", "data", "tutor_rules_beginner.json")
    
    if not os.path.exists(rules_path):
        return {}
        
    try:
        with open(rules_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load rules: {str(e)}")

@router.post("/beginner-rules")
def save_beginner_rules(
    data: dict,
    current_user: UserAccount = Depends(get_current_user)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
        
    import os
    import json
    rules_path = os.path.join(os.getcwd(), "app", "data", "tutor_rules_beginner.json")
    
    try:
        with open(rules_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return {"status": "ok", "message": "Rules saved"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save rules: {str(e)}")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save rules: {str(e)}")

