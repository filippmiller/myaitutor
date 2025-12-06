import { useState, useEffect } from 'react';

interface LessonStep {
    step: number;
    name: string;
    description: string;
    example: string;
}

interface GrammarRule {
    rule: string;
    explanation: string;
}

interface CoreCategories {
    [key: string]: string[];
}

interface ProgressionMap {
    [key: string]: string[];
}

interface BeginnerRulesData {
    level?: string;
    goals?: string[];
    core_categories?: CoreCategories;
    lesson_structure?: LessonStep[];
    teaching_principles?: string[];
    grammar_rules?: GrammarRule[];
    forbidden?: string[];
    progression?: ProgressionMap;
    // allow extra fields just in case
    [key: string]: any;
}

function StringListEditor(props: {
    label: string;
    items: string[];
    onChange: (items: string[]) => void;
    placeholder?: string;
}) {
    const { label, items, onChange, placeholder } = props;
    return (
        <div style={{ marginBottom: '1rem' }}>
            <h4 style={{ marginBottom: '0.4rem' }}>{label}</h4>
            {items.length === 0 && (
                <p style={{ color: '#777', fontSize: '0.85rem' }}>Пока пусто. Добавь первый пункт.</p>
            )}
            {items.map((item, idx) => (
                <div key={idx} style={{ display: 'flex', gap: '0.5rem', marginBottom: '0.35rem' }}>
                    <input
                        type="text"
                        value={item}
                        placeholder={placeholder}
                        onChange={e => {
                            const next = [...items];
                            next[idx] = e.target.value;
                            onChange(next);
                        }}
                        style={{
                            flex: 1,
                            padding: '0.35rem 0.5rem',
                            borderRadius: 4,
                            border: '1px solid #444',
                            background: '#111',
                            color: '#eee',
                            fontSize: '0.9rem',
                            fontFamily: 'inherit',
                        }}
                    />
                    <button
                        type="button"
                        onClick={() => onChange(items.filter((_, i) => i !== idx))}
                        style={{
                            padding: '0.3rem 0.7rem',
                            borderRadius: 4,
                            border: '1px solid #555',
                            background: '#1f2933',
                            color: '#eee',
                            cursor: 'pointer',
                            fontSize: '0.8rem',
                        }}
                    >
                        Удалить
                    </button>
                </div>
            ))}
            <button
                type="button"
                onClick={() => onChange([...items, ''])}
                style={{
                    padding: '0.35rem 0.8rem',
                    borderRadius: 4,
                    border: '1px solid #4CAF50',
                    background: '#064e3b',
                    color: '#e6fffa',
                    cursor: 'pointer',
                    fontSize: '0.8rem',
                    marginTop: '0.25rem',
                }}
            >
                + Добавить
            </button>
        </div>
    );
}

function LessonStructureEditor(props: {
    steps: LessonStep[];
    onChange: (steps: LessonStep[]) => void;
}) {
    const { steps, onChange } = props;
    const updateStep = (idx: number, field: keyof LessonStep, value: string) => {
        const next = steps.map((s, i) => (i === idx ? { ...s, [field]: field === 'step' ? Number(value) || 0 : value } : s));
        onChange(next);
    };

    return (
        <div style={{ marginBottom: '1rem' }}>
            <h4 style={{ marginBottom: '0.4rem' }}>Структура урока (шаги)</h4>
            {steps.length === 0 && (
                <p style={{ color: '#777', fontSize: '0.85rem' }}>Пока нет шагов. Добавь первый шаг сценария.</p>
            )}
            {steps.map((step, idx) => (
                <div
                    key={idx}
                    style={{
                        border: '1px solid #333',
                        borderRadius: 6,
                        padding: '0.5rem 0.6rem',
                        marginBottom: '0.5rem',
                        background: '#111',
                    }}
                >
                    <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '0.35rem' }}>
                        <input
                            type="number"
                            value={step.step}
                            onChange={e => updateStep(idx, 'step', e.target.value)}
                            style={{
                                width: '70px',
                                padding: '0.25rem 0.4rem',
                                borderRadius: 4,
                                border: '1px solid #444',
                                background: '#000',
                                color: '#eee',
                            }}
                        />
                        <input
                            type="text"
                            value={step.name}
                            onChange={e => updateStep(idx, 'name', e.target.value)}
                            placeholder="internal name (например, greeting)"
                            style={{
                                flex: 1,
                                padding: '0.25rem 0.4rem',
                                borderRadius: 4,
                                border: '1px solid #444',
                                background: '#000',
                                color: '#eee',
                                fontSize: '0.9rem',
                            }}
                        />
                        <button
                            type="button"
                            onClick={() => onChange(steps.filter((_, i) => i !== idx))}
                            style={{
                                padding: '0.25rem 0.7rem',
                                borderRadius: 4,
                                border: '1px solid #555',
                                background: '#1f2933',
                                color: '#eee',
                                cursor: 'pointer',
                                fontSize: '0.8rem',
                            }}
                        >
                            Удалить
                        </button>
                    </div>
                    <textarea
                        value={step.description}
                        onChange={e => updateStep(idx, 'description', e.target.value)}
                        placeholder="Кратко опиши, что делает этот шаг"
                        style={{
                            width: '100%',
                            minHeight: '40px',
                            marginBottom: '0.3rem',
                            borderRadius: 4,
                            border: '1px solid #444',
                            background: '#000',
                            color: '#eee',
                            fontSize: '0.85rem',
                        }}
                    />
                    <textarea
                        value={step.example}
                        onChange={e => updateStep(idx, 'example', e.target.value)}
                        placeholder="Пример реплики/мини-сценария"
                        style={{
                            width: '100%',
                            minHeight: '40px',
                            borderRadius: 4,
                            border: '1px solid #444',
                            background: '#000',
                            color: '#eee',
                            fontSize: '0.85rem',
                        }}
                    />
                </div>
            ))}
            <button
                type="button"
                onClick={() =>
                    onChange([
                        ...steps,
                        { step: steps.length + 1, name: '', description: '', example: '' },
                    ])
                }
                style={{
                    padding: '0.35rem 0.8rem',
                    borderRadius: 4,
                    border: '1px solid #4B5563',
                    background: '#111827',
                    color: '#e5e7eb',
                    cursor: 'pointer',
                    fontSize: '0.8rem',
                    marginTop: '0.25rem',
                }}
            >
                + Добавить шаг
            </button>
        </div>
    );
}

export default function AdminBeginnerRules() {
    const [rules, setRules] = useState<BeginnerRulesData | null>(null);
    const [loading, setLoading] = useState(true);
    const [msg, setMsg] = useState('');
    const [error, setError] = useState('');
    const [saving, setSaving] = useState(false);
    const [showJson, setShowJson] = useState(false);

    useEffect(() => {
        fetch('/api/admin/beginner-rules')
            .then(res => res.json())
            .then((data) => {
                // Merge with sensible defaults so UI always has arrays
                const base: BeginnerRulesData = {
                    level: 'absolute_beginner',
                    goals: [],
                    core_categories: {
                        pronouns: [],
                        basic_verbs: [],
                        greetings: [],
                        questions: [],
                        useful_phrases: [],
                    },
                    lesson_structure: [],
                    teaching_principles: [],
                    grammar_rules: [],
                    forbidden: [],
                    progression: { after_5_lessons: [] },
                };
                const merged: BeginnerRulesData = {
                    ...base,
                    ...(data || {}),
                    core_categories: {
                        ...(base.core_categories || {}),
                        ...((data && data.core_categories) || {}),
                    },
                    progression: {
                        ...(base.progression || {}),
                        ...((data && data.progression) || {}),
                    },
                };
                setRules(merged);
                setLoading(false);
            })
            .catch(err => {
                console.error(err);
                setError('Failed to load beginner rules');
                setLoading(false);
            });
    }, []);

    const save = async () => {
        if (!rules) return;
        setSaving(true);
        setMsg('');
        setError('');
        try {
            const res = await fetch('/api/admin/beginner-rules', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(rules),
            });
            if (res.ok) {
                setMsg('Правила сохранены');
            } else {
                const err = await res.json().catch(() => ({}));
                throw new Error(err.detail || res.statusText);
            }
        } catch (e: any) {
            console.error(e);
            setError(`Ошибка при сохранении: ${String(e.message || e)}`);
        } finally {
            setSaving(false);
        }
    };

    if (loading) return <p>Загружаем правила для абсолютных новичков...</p>;
    if (!rules) return <p style={{ color: 'salmon' }}>Не удалось загрузить правила.</p>;

    const core = rules.core_categories || {};
    const progression = rules.progression || {};

    return (
        <div>
            <h3>Absolute Beginner Curriculum</h3>
            <p style={{ color: '#888', marginBottom: '1rem' }}>
                Здесь ты можешь в удобном виде отредактировать базовый набор правил/шаблонов для уровня A1
                (Absolute Beginner). Эти данные попадают в system prompt перед началом урока.
            </p>

            {error && (
                <div style={{ marginBottom: '0.75rem', padding: '0.6rem 0.8rem', background: '#742a2a', color: '#fee', borderRadius: 4 }}>
                    {error}
                </div>
            )}
            {msg && (
                <div style={{ marginBottom: '0.75rem', padding: '0.6rem 0.8rem', background: '#22543d', color: '#e6fffa', borderRadius: 4 }}>
                    {msg}
                </div>
            )}

            <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: '1.5rem', alignItems: 'flex-start' }}>
                {/* Left column: main pedagogical rules */}
                <div>
                    <StringListEditor
                        label="Цели курса (goals)"
                        items={rules.goals || []}
                        onChange={(items) => setRules(prev => prev ? { ...prev, goals: items } : prev)}
                        placeholder="Например: Научить понимать и произносить базовые фразы"
                    />

                    <StringListEditor
                        label="Принципы преподавания (teaching_principles)"
                        items={rules.teaching_principles || []}
                        onChange={(items) => setRules(prev => prev ? { ...prev, teaching_principles: items } : prev)}
                        placeholder="Короткие, понятные правила — что можно/нужно делать на уроке"
                    />

                    <StringListEditor
                        label="Запрещено (forbidden)"
                        items={rules.forbidden || []}
                        onChange={(items) => setRules(prev => prev ? { ...prev, forbidden: items } : prev)}
                        placeholder="Например: не использовать сложные времена"
                    />

                    <StringListEditor
                        label="Прогрессия после 5 уроков (progression.after_5_lessons)"
                        items={progression.after_5_lessons || []}
                        onChange={(items) =>
                            setRules(prev =>
                                prev ? { ...prev, progression: { ...(prev.progression || {}), after_5_lessons: items } } : prev,
                            )
                        }
                        placeholder="Что меняется / добавляется после первых пяти уроков"
                    />
                </div>

                {/* Right column: словари и структура урока */}
                <div>
                    <div style={{ marginBottom: '1rem', border: '1px solid #333', borderRadius: 6, padding: '0.6rem' }}>
                        <h4 style={{ marginBottom: '0.4rem' }}>Базовый словарь (core_categories)</h4>
                        <StringListEditor
                            label="Местоимения"
                            items={core.pronouns || []}
                            onChange={(items) =>
                                setRules(prev =>
                                    prev ? {
                                        ...prev,
                                        core_categories: { ...(prev.core_categories || {}), pronouns: items },
                                    } : prev,
                                )
                            }
                        />
                        <StringListEditor
                            label="Базовые глаголы"
                            items={core.basic_verbs || []}
                            onChange={(items) =>
                                setRules(prev =>
                                    prev ? {
                                        ...prev,
                                        core_categories: { ...(prev.core_categories || {}), basic_verbs: items },
                                    } : prev,
                                )
                            }
                        />
                        <StringListEditor
                            label="Приветствия"
                            items={core.greetings || []}
                            onChange={(items) =>
                                setRules(prev =>
                                    prev ? {
                                        ...prev,
                                        core_categories: { ...(prev.core_categories || {}), greetings: items },
                                    } : prev,
                                )
                            }
                        />
                        <StringListEditor
                            label="Вопросительные слова"
                            items={core.questions || []}
                            onChange={(items) =>
                                setRules(prev =>
                                    prev ? {
                                        ...prev,
                                        core_categories: { ...(prev.core_categories || {}), questions: items },
                                    } : prev,
                                )
                            }
                        />
                        <StringListEditor
                            label="Полезные фразы"
                            items={core.useful_phrases || []}
                            onChange={(items) =>
                                setRules(prev =>
                                    prev ? {
                                        ...prev,
                                        core_categories: { ...(prev.core_categories || {}), useful_phrases: items },
                                    } : prev,
                                )
                            }
                        />
                    </div>

                    <LessonStructureEditor
                        steps={rules.lesson_structure || []}
                        onChange={(steps) => setRules(prev => (prev ? { ...prev, lesson_structure: steps } : prev))}
                    />

                    <div style={{ marginBottom: '1rem' }}>
                        <h4 style={{ marginBottom: '0.4rem' }}>Грамматические мини-правила (grammar_rules)</h4>
                        {(rules.grammar_rules || []).map((gr, idx) => (
                            <div
                                key={idx}
                                style={{
                                    border: '1px solid #333',
                                    borderRadius: 6,
                                    padding: '0.5rem 0.6rem',
                                    marginBottom: '0.4rem',
                                    background: '#111',
                                }}
                            >
                                <input
                                    type="text"
                                    value={gr.rule}
                                    placeholder="Формула: I want = Я хочу"
                                    onChange={e => {
                                        const copy = [...(rules.grammar_rules || [])];
                                        copy[idx] = { ...copy[idx], rule: e.target.value };
                                        setRules(prev => (prev ? { ...prev, grammar_rules: copy } : prev));
                                    }}
                                    style={{
                                        width: '100%',
                                        marginBottom: '0.3rem',
                                        borderRadius: 4,
                                        border: '1px solid #444',
                                        background: '#000',
                                        color: '#eee',
                                        fontSize: '0.9rem',
                                        padding: '0.25rem 0.4rem',
                                    }}
                                />
                                <textarea
                                    value={gr.explanation}
                                    placeholder="Короткое объяснение по-русски"
                                    onChange={e => {
                                        const copy = [...(rules.grammar_rules || [])];
                                        copy[idx] = { ...copy[idx], explanation: e.target.value };
                                        setRules(prev => (prev ? { ...prev, grammar_rules: copy } : prev));
                                    }}
                                    style={{
                                        width: '100%',
                                        minHeight: '40px',
                                        borderRadius: 4,
                                        border: '1px solid #444',
                                        background: '#000',
                                        color: '#eee',
                                        fontSize: '0.85rem',
                                    }}
                                />
                                <button
                                    type="button"
                                    onClick={() => {
                                        const copy = (rules.grammar_rules || []).filter((_, i) => i !== idx);
                                        setRules(prev => (prev ? { ...prev, grammar_rules: copy } : prev));
                                    }}
                                    style={{
                                        marginTop: '0.3rem',
                                        padding: '0.25rem 0.7rem',
                                        borderRadius: 4,
                                        border: '1px solid #555',
                                        background: '#1f2933',
                                        color: '#eee',
                                        cursor: 'pointer',
                                        fontSize: '0.8rem',
                                    }}
                                >
                                    Удалить правило
                                </button>
                            </div>
                        ))}
                        <button
                            type="button"
                            onClick={() =>
                                setRules(prev =>
                                    prev
                                        ? {
                                            ...prev,
                                            grammar_rules: [
                                                ...(prev.grammar_rules || []),
                                                { rule: '', explanation: '' },
                                            ],
                                        }
                                        : prev,
                                )
                            }
                            style={{
                                padding: '0.35rem 0.8rem',
                                borderRadius: 4,
                                border: '1px solid #4B5563',
                                background: '#111827',
                                color: '#e5e7eb',
                                cursor: 'pointer',
                                fontSize: '0.8rem',
                            }}
                        >
                            + Добавить правило
                        </button>
                    </div>
                </div>
            </div>

            <div style={{ marginTop: '1rem', display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                <button
                    onClick={save}
                    disabled={saving}
                    style={{
                        padding: '0.6rem 1.4rem',
                        borderRadius: 6,
                        border: 'none',
                        backgroundColor: saving ? '#4B5563' : '#4CAF50',
                        color: 'white',
                        cursor: saving ? 'not-allowed' : 'pointer',
                        fontWeight: 600,
                    }}
                >
                    {saving ? 'Saving...' : 'Save Beginner Rules'}
                </button>

                <button
                    type="button"
                    onClick={() => setShowJson(v => !v)}
                    style={{
                        padding: '0.4rem 0.9rem',
                        borderRadius: 6,
                        border: '1px solid #4B5563',
                        background: '#111827',
                        color: '#e5e7eb',
                        cursor: 'pointer',
                        fontSize: '0.8rem',
                    }}
                >
                    {showJson ? 'Скрыть raw JSON' : 'Показать raw JSON (для продвинутой правки)'}
                </button>
            </div>

            {showJson && (
                <div style={{ marginTop: '1rem' }}>
                    <h4>Raw JSON (read-only справка)</h4>
                    <textarea
                        readOnly
                        value={JSON.stringify(rules, null, 2)}
                        style={{
                            width: '100%',
                            height: '320px',
                            fontFamily: 'monospace',
                            background: '#050505',
                            color: '#e5e7eb',
                            border: '1px solid #374151',
                            borderRadius: 6,
                            padding: '0.75rem',
                            fontSize: '0.85rem',
                        }}
                        spellCheck={false}
                    />
                </div>
            )}
        </div>
    );
}
