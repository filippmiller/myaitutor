# Admin Voice Rule Builder & Debug Logging Improvements — 2025-12-06

Этот документ — живой журнал (append-only) всех улучшений, которые мы сделали вокруг:
- интерфейса **Admin Voice Rule Builder** (голосовое создание правил);
- логики **pause/resume** для голосовых уроков;
- системы **debug logging** и просмотра обмена с OpenAI (prompt’ы и ответы);
- фиксов, связанных с OpenAI Realtime/STT и ошибками деплоя на Railway.

## 2025-12-06 — Сессия 1: Voice Rule Builder UX + Pause/Resume + Debug Logging

### 1. Улучшение Admin Voice Rule Builder (Voice Rules)

**Цель:** сделать голосовой конструктор правил удобным: real-time транскрипция во время записи, быстрый health-check ключа OpenAI и отсутствие ложных ошибок.

**Сделано:**

1. **Health-check эндпоинт для Voice Rules**
   - Добавлен эндпоинт `GET /api/admin/voice-rules/health` в `app/api/routes/admin_voice_rules.py`.
   - Проверяет, что существует действующий OpenAI API key.
   - Важно: ключ берётся либо из `AppSettings.openai_api_key`, либо из окружения `OPENAI_API_KEY` (как и для основного голосового урока).
   - Возвращает `HealthResponse { openai_key_set: bool }` без выброса 400 наружу, чтобы фронт мог спокойно решить, можно ли начинать запись.

2. **Frontend: pre-check перед Start Recording**
   - В `frontend/src/components/AdminVoiceRules.tsx` добавлен вызов `checkHealth()` внутри `startRecording()`.
   - Если `openai_key_set == false`, показывается дружелюбная ошибка, и запись не стартует вовсе (чтобы не тратить время на длинную запись без ключа).

3. **Real-time транскрипция (chunk STT)**
   - Логика записи изменена: `MediaRecorder.start(2000)` с `ondataavailable`, каждую порцию отправляем на `POST /api/admin/voice-rules/transcribe-chunk`.
   - Backend:
     - Эндпоинт `transcribe_chunk` принимает `UploadFile` и вызывает `OpenAIVoiceEngine.transcribe()`.
     - Передаём в Whisper корректное имя файла с расширением на основе `audio_file.content_type` (`webm/ogg/wav/mp4/mp3`), чтобы OpenAI корректно распознал формат.
     - На типичную ошибку `Invalid file format` от Whisper (особенно на очень коротких чанках) мы теперь **не роняем** весь процесс: логируем варнинг и возвращаем пустой `text=""`, чтобы UI продолжал работу.
   - Фронт накапливает транскрипцию в `transcript` из возвращаемых текстов.

4. **Генерация правил после Stop (generate-from-text)**
   - Frontend: после `mediaRecorder.stop()` мы не шлём весь audio‑blob, а используем уже собранный `transcript` (из chunk STT) и вызываем `POST /api/admin/voice-rules/generate-from-text`.
   - Backend: `generate_from_text` использует общий helper `_generate_rule_drafts_from_transcript(...)` для вызова Chat Completions с JSON‑schema и создаёт `RuleGenerationLog`.

5. **UI изменения**
   - Обновлён текст в панели transcript: теперь явно сказано, что транскрипция появится *во время записи*.
   - Кнопка `Start Recording`/`Stop Recording` корректно меняет статус, показывает `Status: Recording.../Paused/Error`.

**Проблемы и решения:**

- Проблема: health-check сначала смотрел только в `AppSettings.openai_api_key`, из-за чего в продакшене (где ключ был только в ENV) показывалась ошибка «OpenAI API key not configured».
  - Фикс: `_get_settings_or_400` теперь учитывает и ENV, и БД, и возвращает объект `AppSettings` с заполненным `openai_api_key`.
- Проблема: Whisper иногда отвечал 400 `Invalid file format` на короткие webm‑чанки, что вызывало 500 и красный баннер.
  - Фикс: передаём осмысленное имя файла (`admin-voice-chunk.<ext>`), а именно для этой ошибки делаем soft‑fail с пустым текстом.

### 2. Pause/Resume для голосовых уроков (Realtime + Legacy)

**Цель:** вместо полного завершения урока иметь возможность поставить его на паузу и продолжить позже с коротким «welcome back» и напоминанием, что делали до перерыва.

**Сделано:**

1. **Модель `LessonPauseEvent`**
   - В `app/models.py` добавлена таблица:
     - `lesson_pause_events (LessonPauseEvent)`
     - поля: `id`, `lesson_session_id`, `paused_at`, `resumed_at`, `summary_text`, `reason`.
   - `LessonSession` не меняли по схеме (только поле `status` уже существовало) — вся аналитика пауз живёт в отдельной таблице, чтобы не ломать миграции.

2. **Pause/Resume в WebSocket (`/api/ws/voice`)**
   - В `voice_websocket`:
     - читаем query‑параметры `lesson_session_id` и `resume=1` для resuming существующей сессии;
     - передаём `lesson_session` и флаг `is_resume` в `run_realtime_session` и `run_legacy_session`.
   - При первом подключении создаём `LessonSession` (как раньше).
   - На паузе:
     - фронт отправляет `{"type":"system_event","event":"lesson_paused"}`;
     - backend:
       - собирает диалог из `LessonTurn` и вызывает Chat Completions, чтобы получить 1–2 предложения резюме («Before the break, ...»);
       - создаёт `LessonPauseEvent` с `summary_text`;
       - ставит `LessonSession.status = "paused"`;
       - закрывает Realtime WS и frontend WS с кодом/причиной `lesson_paused`.
   - На резюме:
     - фронт открывает новый WS с `?lesson_session_id=<id>&resume=1`;
     - backend находит `LessonSession`, помечает как `active` и закрывает последний `LessonPauseEvent.resumed_at`.

3. **Системный промпт с учётом паузы/резюме**
   - `build_tutor_system_prompt(session, user, lesson_session_id, is_resume)` теперь:
     - читает список `LessonPauseEvent` для сессии;
     - добавляет в prompt блок **Pause / Resume Context** с количеством пауз и последним резюме;
     - если `is_resume=True`, добавляет чёткую секцию:

       > **RESUMED LESSON BEHAVIOR (AFTER A BREAK):**
       > - В следующем сообщении сделать короткое «welcome back»;
       > - кратко напомнить, что делали до перерыва (если есть summary);
       > - сразу продолжать активность, не повторяя полное введение/план урока.

4. **Frontend Student UI: Pause / Resume кнопки**
   - В `Student.tsx`:
     - вместо одной кнопки `Start/End` теперь:
       - `Start Live Lesson / Resume Lesson` (в зависимости от `connectionStatus` и `lessonSessionIdRef`);
       - в режиме активного соединения отображаются две кнопки: **Pause Lesson** (жёлтая) и **End Lesson** (красная).
     - `pauseLesson()` отправляет `lesson_paused`, останавливает микрофон и TTS, но не обнуляет `lessonSessionIdRef`.
     - при закрытии WS с reason `lesson_paused` ставим статус `Paused`.
     - новый вызов `startLesson(true)` идёт с query `lesson_session_id` и `resume=1`, backend понимает, что это продолжение.

**Проблемы и решения:**

- Важно было **не менять** схему `lesson_sessions` в продакшен‑БД (Railway). Метаданные пауз вынесли в `LessonPauseEvent` и используем их только при построении prompt’а и аналитике.

### 3. Debug logging: live‑терминал + файл‑логи + Admin UI

**Цель:** на время разработки видеть полный обмен с OpenAI: какие system‑prompt’ы и запросы мы посылаем, какие ответы модель даёт, как работает pause/resume и генерация правил.

**Сделано:**

1. **Таблица DebugSettings и флаг voice_logging_enabled**
   - В `app/models.py`:

     ```python
     class DebugSettings(SQLModel, table=True):
         __tablename__ = "debug_settings"
         id: int = Field(default=1, primary_key=True)
         voice_logging_enabled: bool = Field(default=False)
     ```

   - В `app/api/admin.py`:
     - эндпоинты `GET/POST /api/admin/debug-settings` для чтения/записи флага.

   - В `Admin.tsx` (вкладка Settings):
     - новый чекбокс **Enable voice debug logging (show OpenAI traffic in student UI)**;
     - при сохранении настроек вызываются и `/settings`, и `/debug-settings`.

2. **Live‑debug через WebSocket в Student UI**

   - В `voice_ws.run_realtime_session` и `run_legacy_session` добавлен helper `_send_debug(direction, channel, payload)`:
     - чистит большие base64‑аудиополя;
     - шлёт фронту JSON:

       ```json
       {
         "type": "debug",
         "direction": "to_openai" | "from_openai" | "from_frontend",
         "channel": "realtime" | "realtime_greeting" | "pause_summary" | "config",
         "payload": { ... }
       }
       ```

   - На фронте `Student.tsx`:
     - новые состояния: `debugEnabled`, `debugLines`;
     - при получении `lesson_info` сервер также присылает `debug_enabled` (зависит от DebugSettings);
     - при получении `msg.type === 'debug'` формируем строку `[..., ..., ...]` и добавляем в `debugLines`.
     - под основным чатом появился блок **Debug Console (OpenAI traffic)**, который показывает все эти строки во время урока.

3. **Файловое логирование per‑lesson (JSONL)**

   - В `voice_ws.py`:
     - объявлен `OPENAI_LOG_DIR = static/openai_logs`;
     - функция `append_openai_log(lesson_session_id, entry)` пишет строки в файл:

       ```
       static/openai_logs/lesson_<lesson_session_id>.jsonl
       ```

       где каждая строка — JSON с полями: `ts`, `lesson_session_id`, `direction`, `channel`, `payload`.

   - `_send_debug(...)` теперь делает **две** вещи:
     - отправляет debug‑пакет фронту;
     - вызывает `append_openai_log(...)` для записи в файл.

4. **Admin UI для просмотра логов по уроку**

   - В `app/api/admin.py` добавлен эндпоинт `GET /api/admin/lesson-logs`:
     - без параметров: возвращает список доступных лог‑файлов `lesson_*.jsonl` с `lesson_session_id` и `updated_at`;
     - с `lesson_session_id`: читает файл, возвращает последние `limit_lines` строк как `entries`.

   - В `frontend/src/components/AdminLessonPrompts.tsx`:
     - помимо списка prompt‑логов, теперь при выборе урока делается запрос на `/api/admin/lesson-logs?lesson_session_id=...`;
     - в правой панели под System Prompt и Greeting Prompt появился блок **OpenAI Traffic Log (debug)**:
       - показывает содержимое файла в виде читаемого текста:

         ```
         [timestamp][direction][channel]
         { pretty-printed payload }
         ```

       - если логов нет (debug был выключен), выводится дружелюбное сообщение.

Так админ может задним числом открыть любой урок и увидеть:
- точный `session.update` с system‑prompt;
- все greeting‑события;
- паузы и резюме;
- и все STT/LLM‑запросы, связанные с уроком.

### 4. Инциденты и фиксы деплоя Railway

В процессе были пойманы и исправлены несколько регрессий:

1. **Crash из-за отсутствия BaseModel/get_current_user в `admin.py`**
   - Во время правок добавления DebugSettings из файла пропали импорты `BaseModel` и `get_current_user`, из‑за чего Uvicorn падал при старте.
   - Логи Railway подсказали `NameError: name 'BaseModel' is not defined`, затем `NameError: name 'get_current_user' is not defined`.
   - Исправлено добавлением правильных импортов и чисткой дубликатов `os/json`.

2. **Health‑проверка Voice Rules не учитывала `OPENAI_API_KEY`**
   - В проде использовали только ENV‑ключ, а `AppSettings` могли быть пустыми, поэтому health возвращал `openai_key_set=false`.
   - Исправлено через `_get_settings_or_400`, как описано выше.

3. **Серии 400 Invalid file format от Whisper в Admin Voice Rule Builder**
   - Root cause: очень короткие или “странные” webm‑чанки от MediaRecorder + неуказанный/неподходящий filename/extension.
   - Исправления:
     - передача корректного filename с расширением в `OpenAIVoiceEngine.transcribe`;
     - soft‑обработка именно этой ошибки в `transcribe_chunk`, чтобы не показывать пользователю 500 и не ломать сессию.

---

Документ остаётся открытым для дальнейших дописок: любые новые улучшения Voice Rule Builder’а, пауз/резюме, debug logging’а и связанных багфиксов будут добавляться ниже как новые разделы с датой и кратким описанием изменений.
