-- Add columns to lesson_sessions
ALTER TABLE lesson_sessions ADD COLUMN IF NOT EXISTS language_mode VARCHAR;
ALTER TABLE lesson_sessions ADD COLUMN IF NOT EXISTS language_level INTEGER;
ALTER TABLE lesson_sessions ADD COLUMN IF NOT EXISTS language_chosen_at TIMESTAMP WITHOUT TIME ZONE;

-- Ensure tutor_system_rules table exists (usually handled by app, but good to be safe or for seeding)
CREATE TABLE IF NOT EXISTS tutor_system_rules (
    id SERIAL PRIMARY KEY,
    rule_key VARCHAR NOT NULL,
    rule_text VARCHAR NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    enabled BOOLEAN NOT NULL DEFAULT TRUE
);

-- Seed Tutor System Rules
INSERT INTO tutor_system_rules (rule_key, rule_text, sort_order, enabled)
SELECT 'greeting.addressing', 'If the student has a preferred form of address, use it. If not, politely ask how they would like to be addressed.', 10, true
WHERE NOT EXISTS (SELECT 1 FROM tutor_system_rules WHERE rule_key = 'greeting.addressing');

INSERT INTO tutor_system_rules (rule_key, rule_text, sort_order, enabled)
SELECT 'greeting.last_lesson', 'Briefly mention the topic of the last lesson if available to provide continuity.', 20, true
WHERE NOT EXISTS (SELECT 1 FROM tutor_system_rules WHERE rule_key = 'greeting.last_lesson');

INSERT INTO tutor_system_rules (rule_key, rule_text, sort_order, enabled)
SELECT 'adaptation.level', 'Strictly adapt your vocabulary and grammar to the student''s level. Use simple sentences for A1-A2.', 30, true
WHERE NOT EXISTS (SELECT 1 FROM tutor_system_rules WHERE rule_key = 'adaptation.level');
