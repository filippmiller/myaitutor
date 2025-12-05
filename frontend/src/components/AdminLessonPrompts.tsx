import { useEffect, useState } from 'react';

interface LessonPromptLog {
    mode?: string;
    lesson_session_id?: number;
    user_account_id?: number;
    user_email?: string;
    student_name?: string;
    english_level?: string;
    tts_engine?: string;
    voice_id?: string;
    stt_language?: string;
    system_prompt?: string;
    greeting_event_prompt?: string;
    created_at?: string;
}

export default function AdminLessonPrompts() {
    const [logs, setLogs] = useState<LessonPromptLog[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [selected, setSelected] = useState<LessonPromptLog | null>(null);

    const loadLogs = async () => {
        setLoading(true);
        setError(null);
        try {
            const res = await fetch('/api/admin/lesson-prompts?limit=50');
            if (!res.ok) {
                const err = await res.json().catch(() => ({}));
                throw new Error(err.detail || res.statusText);
            }
            const data = await res.json();
            setLogs(data);
        } catch (e: any) {
            console.error(e);
            setError(String(e));
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        loadLogs();
    }, []);

    return (
        <div style={{ marginTop: '1rem' }}>
            <h3>Lesson Prompt Logs</h3>
            <p style={{ color: '#aaa', fontSize: '0.9rem' }}>
                Здесь можно посмотреть, какой system prompt и greeting prompt мы отправили в OpenAI
                для начала каждого voice-урока.
            </p>

            <div style={{ marginBottom: '0.5rem', display: 'flex', gap: '0.5rem' }}>
                <button onClick={loadLogs} disabled={loading}>
                    {loading ? 'Refreshing...' : 'Refresh Logs'}
                </button>
            </div>

            {error && (
                <div style={{ color: 'salmon', marginBottom: '0.5rem' }}>
                    Error: {error}
                </div>
            )}

            {logs.length === 0 && !loading && (
                <p style={{ color: '#888' }}>No prompt logs yet.</p>
            )}

            {logs.length > 0 && (
                <div style={{ display: 'flex', gap: '1rem', alignItems: 'flex-start' }}>
                    <div style={{ flex: 1 }}>
                        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.9rem' }}>
                            <thead>
                                <tr style={{ borderBottom: '1px solid #444' }}>
                                    <th style={{ textAlign: 'left', padding: '4px' }}>Lesson ID</th>
                                    <th style={{ textAlign: 'left', padding: '4px' }}>Student</th>
                                    <th style={{ textAlign: 'left', padding: '4px' }}>Level</th>
                                    <th style={{ textAlign: 'left', padding: '4px' }}>Mode</th>
                                    <th style={{ textAlign: 'left', padding: '4px' }}>Voice</th>
                                    <th style={{ textAlign: 'left', padding: '4px' }}>STT Lang</th>
                                    <th style={{ textAlign: 'left', padding: '4px' }}>Created</th>
                                </tr>
                            </thead>
                            <tbody>
                                {logs.map(log => (
                                    <tr
                                        key={`${log.lesson_session_id}-${log.created_at}`}
                                        style={{ borderBottom: '1px solid #333', cursor: 'pointer' }}
                                        onClick={() => setSelected(log)}
                                    >
                                        <td style={{ padding: '4px' }}>{log.lesson_session_id ?? '-'}</td>
                                        <td style={{ padding: '4px' }}>
                                            {log.student_name || log.user_email || 'Unknown'}
                                        </td>
                                        <td style={{ padding: '4px' }}>{log.english_level || '-'}</td>
                                        <td style={{ padding: '4px' }}>{log.mode || '-'}</td>
                                        <td style={{ padding: '4px' }}>
                                            {log.tts_engine || 'openai'} / {log.voice_id || 'alloy'}
                                        </td>
                                        <td style={{ padding: '4px' }}>{log.stt_language || '-'}</td>
                                        <td style={{ padding: '4px' }}>
                                            {log.created_at ? new Date(log.created_at).toLocaleString() : '-'}
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>

                    <div style={{ flex: 1 }}>
                        {selected ? (
                            <div style={{ padding: '0.5rem', border: '1px solid #444', borderRadius: '4px' }}>
                                <h4>
                                    Lesson {selected.lesson_session_id} —{' '}
                                    {selected.student_name || selected.user_email || 'Unknown'}
                                </h4>
                                <p style={{ fontSize: '0.85rem', color: '#aaa' }}>
                                    Mode: {selected.mode || '-'} | Level: {selected.english_level || '-'} | Voice:{' '}
                                    {selected.tts_engine || 'openai'} / {selected.voice_id || 'alloy'}
                                </p>

                                <div style={{ marginTop: '0.5rem' }}>
                                    <h5>System Prompt</h5>
                                    <textarea
                                        readOnly
                                        style={{ width: '100%', height: '200px', background: '#111', color: '#eee', fontSize: '0.8rem' }}
                                        value={selected.system_prompt || ''}
                                    />
                                </div>

                                <div style={{ marginTop: '0.5rem' }}>
                                    <h5>Greeting Event Prompt</h5>
                                    <textarea
                                        readOnly
                                        style={{ width: '100%', height: '120px', background: '#111', color: '#eee', fontSize: '0.8rem' }}
                                        value={selected.greeting_event_prompt || ''}
                                    />
                                </div>
                            </div>
                        ) : (
                            <p style={{ color: '#888' }}>Select a lesson on the left to see its prompts.</p>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
}