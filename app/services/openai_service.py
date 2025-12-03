import os
from openai import OpenAI
from app.models import UserProfile, AppSettings, SessionMessage, UserState
from sqlmodel import Session, select
import json

SYSTEM_TUTOR_PROMPT = """You are a personal English tutor for a Russian-speaking student.

Context about the student:
You receive their name, English level (A1–C1), goals and pains.
You also receive lists of weak_words (words they struggle with) and known_words.
You receive a short dialog history of recent messages.

Your goals:
Speak slowly, clearly, with pauses, using simple sentences.
Always adapt your language to the student’s level:
A1–A2: very simple words and short phrases.
B1–B2: everyday language, no complex news-style or academic language.
Be patient and friendly. Never criticize harshly.

Behavior in each answer:
Main reply:
Answer in English.
Use simple, clear English appropriate to the student’s level.
Imagine you are speaking slowly. You may sometimes insert hints like “(short pause)” to suggest natural breaks.

Work with weak words:
Try to reuse 1–3 weak_words in natural sentences.
Show how to use them correctly.

Correcting mistakes:
If the student makes a clear mistake, do NOT give a long grammar lecture.
First, repeat their sentence in correct form.
Then give a short explanation in simple English (and, if needed, one short Russian comment).

Small explanation block at the end:
“New words:” — 2–4 important words with very short explanations.
“Try to say:” — 1 simple sentence the student can repeat.

Language rules:
Default: answer 90–95% in English.
You may add short Russian hints only when absolutely necessary.

Style:
Be positive, supportive, and calm.
Always encourage the student to answer with their own sentence, not just “yes/no”.
"""

def analyze_learning_exchange(
    user_profile: UserProfile | None,
    user_state: UserState | None,
    user_text: str,
    assistant_text: str,
    settings: AppSettings
) -> dict:
    client = OpenAI(api_key=settings.openai_api_key)
    
    # Build context string
    profile_str = ""
    if user_profile:
        profile_str += f"Name: {user_profile.name}, Level: {user_profile.english_level}, Goals: {user_profile.goals}."
    
    words_str = ""
    if user_state:
        words_str += f"Weak words: {user_state.weak_words_json}. Known words: {user_state.known_words_json}."

    prompt = f"""You are an assistant analyzing one short exchange between an English learner and a tutor.

Input:
Learner: "{user_text}"
Tutor: "{assistant_text}"

Context:
{profile_str}
{words_str}

Output JSON with strictly this structure:
{{
  "new_known_words": ["word1", "word2"],
  "new_weak_words": ["word3"],
  "practiced_words": ["word1", "word2", "word3"],
  "grammar_notes": ["short bullet about grammar issue"],
  "session_summary": "one sentence summary",
  "xp_delta": 1,
  "detected_preferences": {{ "preferred_address": "string or null", "preferred_voice": "string or null" }}
}}

Limit:
- new_known_words and new_weak_words should be short (0–5 items).
- Words should be in English, in base form (no duplicates).
- session_summary should be max 1–2 sentences.
- grammar_notes is optional (can be empty array).
- detected_preferences: extract ONLY if the user explicitly states how they want to be addressed or which voice to use. Otherwise null.
"""

    try:
        completion = client.chat.completions.create(
            model=settings.default_model, # Use same model as chat for simplicity
            messages=[
                {"role": "system", "content": "You are a helpful assistant that outputs JSON."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )
        content = completion.choices[0].message.content
        return json.loads(content)
    except Exception as e:
        print(f"Analysis failed: {e}")
        return {
            "new_known_words": [],
            "new_weak_words": [],
            "practiced_words": [],
            "grammar_notes": [],
            "session_summary": None,
            "xp_delta": 1,
        }

async def process_voice_interaction(
    audio_path: str,
    user: UserProfile,
    settings: AppSettings,
    db_session: Session
):
    client = OpenAI(api_key=settings.openai_api_key)
    
    # 1. Transcribe Audio (STT)
    with open(audio_path, "rb") as audio_file:
        transcription = client.audio.transcriptions.create(
            model="whisper-1", 
            file=audio_file
        )
    user_text = transcription.text

    # 2. Save User Message
    user_msg = SessionMessage(
        user_id=user.id, 
        user_account_id=user.user_account_id,
        role="user", 
        content=user_text
    )
    db_session.add(user_msg)
    db_session.commit()

    # 3. Prepare Chat Context
    # Get recent history (last 10 messages)
    history_statement = select(SessionMessage).where(SessionMessage.user_id == user.id).order_by(SessionMessage.created_at.desc()).limit(10)
    history = db_session.exec(history_statement).all()
    history.reverse() # Oldest first

    from app.services.tutor_service import build_tutor_system_prompt
    system_prompt = build_tutor_system_prompt(db_session, user)

    messages = [
        {"role": "system", "content": system_prompt}
    ]
    
    for msg in history:
        messages.append({"role": msg.role, "content": msg.content})
    
    # 4. Call Chat Completion
    completion = client.chat.completions.create(
        model=settings.default_model,
        messages=messages
    )
    assistant_text = completion.choices[0].message.content

    # 5. Save Assistant Message
    asst_msg = SessionMessage(
        user_id=user.id, 
        user_account_id=user.user_account_id,
        role="assistant", 
        content=assistant_text
    )
    db_session.add(asst_msg)
    db_session.commit()

    # 6. Generate Audio (TTS)
    speech_file_path = f"static/audio/response_{asst_msg.id}.mp3"
    os.makedirs("static/audio", exist_ok=True)
    
    # Determine voice
    try:
        prefs = json.loads(user.preferences)
        voice_pref = prefs.get("preferred_voice")
        print(f"DEBUG: User preferences: {prefs}")
        print(f"DEBUG: Selected voice preference: {voice_pref}")
    except Exception as e:
        print(f"DEBUG: Error parsing preferences: {e}")
        voice_pref = None
        
    # Yandex Voices
    yandex_voices = ['alisa', 'alena', 'filipp', 'jane', 'madirus', 'omazh', 'zahar', 'ermil']
    
    if voice_pref in yandex_voices:
        print(f"DEBUG: Attempting Yandex TTS with voice: {voice_pref}")
        try:
            from app.services.yandex_service import YandexService
            import subprocess
            yandex_service = YandexService()
            
            # Save to file
            full_path = os.path.join(os.getcwd(), speech_file_path)
            
            # Use ffmpeg to convert PCM (48k, 16bit, mono) to MP3
            process = subprocess.Popen(
                [
                    "ffmpeg",
                    "-f", "s16le", "-ar", "48000", "-ac", "1", "-i", "pipe:0",
                    "-y", # Overwrite
                    full_path
                ],
                stdin=subprocess.PIPE,
                stderr=subprocess.DEVNULL
            )
            
            for chunk in yandex_service.synthesize_stream(text=assistant_text, voice=voice_pref):
                try:
                    process.stdin.write(chunk)
                except BrokenPipeError:
                    print("DEBUG: ffmpeg stdin broken pipe")
                    break
            
            process.stdin.close()
            process.wait()
            print(f"DEBUG: Yandex TTS successful, saved to {full_path}")
            
            return {
                "user_text": user_text,
                "assistant_text": assistant_text,
                "audio_url": f"/static/audio/response_{asst_msg.id}.mp3"
            }
        except Exception as e:
            print(f"DEBUG: Yandex TTS failed: {e}, falling back to OpenAI")
            import traceback
            traceback.print_exc()
            # Fallback to OpenAI logic below

    # Simple mapping for OpenAI TTS
    # alloy, echo, fable, onyx, nova, shimmer
    voice_map = {
        "male_deep": "onyx",
        "male_neutral": "echo",
        "female_neutral": "shimmer",
        "female_soft": "nova",
        "default": "alloy"
    }
    openai_voice = voice_map.get(voice_pref, "alloy")
    # If the user just said "onyx" or "shimmer", support that too
    if voice_pref in ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]:
        openai_voice = voice_pref

    response = client.audio.speech.create(
        model="tts-1",
        voice=openai_voice,
        input=assistant_text
    )
    
    # Save to file
    full_path = os.path.join(os.getcwd(), speech_file_path)
    response.stream_to_file(full_path)
    
    return {
        "user_text": user_text,
        "assistant_text": assistant_text,
        "audio_url": f"/static/audio/response_{asst_msg.id}.mp3"
    }
