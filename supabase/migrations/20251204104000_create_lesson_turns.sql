CREATE TABLE IF NOT EXISTS lesson_turns (
    id SERIAL PRIMARY KEY,
    session_id INTEGER NOT NULL REFERENCES lesson_sessions(id),
    speaker VARCHAR NOT NULL,
    text VARCHAR NOT NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT timezone('utc', now())
);

CREATE INDEX IF NOT EXISTS idx_lesson_turns_session_id ON lesson_turns(session_id);
