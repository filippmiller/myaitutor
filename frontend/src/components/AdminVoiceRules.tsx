import { useState, useRef } from 'react';

interface RuleDraft {
    scope: string;
    type: string;
    title: string;
    description: string;
    trigger_condition?: any;
    action?: any;
    priority: number;
    selected: boolean;
}

interface DraftResponse {
    transcript: string;
    rules: Omit<RuleDraft, 'selected'>[];
    generation_log_id?: number;
}

interface SaveResponse {
    saved_rules: {
        id: number;
        title: string;
        scope: string;
        type: string;
        priority: number;
    }[];
}

interface HealthResponse {
    openai_key_set: boolean;
}

// Legacy interface from chunk-STT mode (now unused)
// interface ChunkTranscriptionResponse {
//     text: string;
// }
export default function AdminVoiceRules() {
    const [isRecording, setIsRecording] = useState(false);
    const [status, setStatus] = useState<string>('Idle');
    const [transcript, setTranscript] = useState<string>('');
    const [rules, setRules] = useState<RuleDraft[]>([]);
    const [generationLogId, setGenerationLogId] = useState<number | undefined>(undefined);
    const [saving, setSaving] = useState(false);
    const [saveMessage, setSaveMessage] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);

    const mediaRecorderRef = useRef<MediaRecorder | null>(null);
    const transcriptRef = useRef<string>('');
    const audioChunksRef = useRef<Blob[]>([]);

    const checkHealth = async (): Promise<boolean> => {
        setStatus('Checking backend health...');
        try {
            const res = await fetch('/api/admin/voice-rules/health');
            if (!res.ok) {
                const err = await res.json().catch(() => ({}));
                throw new Error(err.detail || res.statusText);
            }
            const data: HealthResponse = await res.json();
            if (!data.openai_key_set) {
                setError('OpenAI API key not configured in admin settings. Зайди в админку и укажи ключ.');
                setStatus('Error');
                return false;
            }
            return true;
        } catch (e: any) {
            console.error(e);
            setError(`Failed to contact backend (/health): ${String(e)}`);
            setStatus('Error');
            return false;
        }
    };

    const startRecording = async () => {
        if (isRecording) return;
        setError(null);
        setSaveMessage(null);
        setTranscript('');
        transcriptRef.current = '';
        setRules([]);
        setGenerationLogId(undefined);

        const ok = await checkHealth();
        if (!ok) {
            return;
        }

        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            const mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
            mediaRecorderRef.current = mediaRecorder;

            audioChunksRef.current = [];

            mediaRecorder.ondataavailable = (e) => {
                if (e.data.size > 0) {
                    // Просто накапливаем чанки, чтобы потом отправить один цельный файл
                    audioChunksRef.current.push(e.data);
                }
            };

            mediaRecorder.onstop = () => {
                // Останавливаем треки микрофона
                mediaRecorder.stream.getTracks().forEach((t) => t.stop());

                const fullBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
                setStatus('Transcribing & generating rules...');
                void transcribeAndDraft(fullBlob);
            };

            // Без timeslice: один цельный blob по завершении записи
            mediaRecorder.start();
            setIsRecording(true);
            setStatus('Recording...');
        } catch (e: any) {
            console.error(e);
            setError('Failed to access microphone.');
            setStatus('Error');
        }
    };

    const stopRecording = () => {
        if (!isRecording || !mediaRecorderRef.current) return;
        setIsRecording(false);
        setStatus('Finishing recording...');
        mediaRecorderRef.current.stop();
    };

    const transcribeAndDraft = async (blob: Blob) => {
        try {
            const form = new FormData();
            form.append('audio_file', blob, 'recording.webm');

            const res = await fetch('/api/admin/voice-rules/transcribe-and-draft', {
                method: 'POST',
                body: form,
            });

            if (!res.ok) {
                const err = await res.json().catch(() => ({}));
                throw new Error(err.detail || res.statusText);
            }

            const data: DraftResponse = await res.json();

            if (data.transcript) {
                transcriptRef.current = data.transcript;
                setTranscript(data.transcript);
            }

            const draftRules: RuleDraft[] = (data.rules || []).map((r) => ({
                ...r,
                priority: (r as any).priority ?? 0,
                selected: true,
            }));

            setRules(draftRules);
            setGenerationLogId(data.generation_log_id);
            setStatus('Draft ready');
        } catch (e: any) {
            console.error(e);
            setError(`Failed to transcribe and generate rules: ${String(e)}`);
            setStatus('Error');
        }
    };

    const toggleRuleSelected = (index: number) => {
        setRules((prev) =>
            prev.map((r, i) => (i === index ? { ...r, selected: !r.selected } : r)),
        );
    };

    const discardDraft = () => {
        setTranscript('');
        transcriptRef.current = '';
        setRules([]);
        setGenerationLogId(undefined);
        setSaveMessage(null);
        setError(null);
        setStatus('Idle');
    };

    const saveSelectedRules = async () => {
        const selected = rules.filter((r) => r.selected);
        if (selected.length === 0) {
            setSaveMessage('No rules selected to save.');
            return;
        }

        setSaving(true);
        setSaveMessage(null);
        setError(null);

        try {
            const body = {
                generation_log_id: generationLogId,
                rules: selected.map(({ selected: _sel, ...rest }) => rest),
            };

            const res = await fetch('/api/admin/voice-rules/save', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
            });

            if (!res.ok) {
                const err = await res.json().catch(() => ({}));
                throw new Error(err.detail || res.statusText);
            }

            const data: SaveResponse = await res.json();
            const count = data.saved_rules?.length ?? 0;
            if (count > 0) {
                const ids = data.saved_rules.map((r) => r.id).join(', ');
                setSaveMessage(`Saved ${count} rule(s): IDs ${ids}`);
            } else {
                setSaveMessage('No rules were saved (empty response).');
            }
        } catch (e: any) {
            console.error(e);
            setError(`Failed to save rules: ${String(e)}`);
        } finally {
            setSaving(false);
        }
    };

    const prettyJson = (value: any) => {
        try {
            return JSON.stringify(value, null, 2);
        } catch {
            return String(value);
        }
    };

    return (
        <div>
            <h3>Voice Rule Builder</h3>
            <p style={{ color: '#888', marginBottom: '1rem' }}>
                Наговаривай сценарии уроков голосом. Мы превратим их в структурированные правила, покажем
                транскрипт и черновик правил, а потом сохраним выбранные в базу.
            </p>

            {/* Recorder Controls */}
            <div style={{ marginBottom: '1rem', display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
                <button
                    onClick={isRecording ? stopRecording : startRecording}
                    style={{
                        padding: '0.6rem 1.2rem',
                        borderRadius: '6px',
                        border: 'none',
                        backgroundColor: isRecording ? '#e53e3e' : '#38a169',
                        color: 'white',
                        cursor: 'pointer',
                        fontWeight: 600,
                    }}
                >
                    {isRecording ? 'Stop Recording' : 'Start Recording'}
                </button>
                <span style={{ color: '#aaa', fontSize: '0.9rem' }}>Status: {status}</span>
                <button
                    onClick={discardDraft}
                    disabled={isRecording}
                    style={{
                        padding: '0.4rem 0.9rem',
                        borderRadius: '6px',
                        border: '1px solid #444',
                        background: '#1a1a1a',
                        color: '#ddd',
                        cursor: isRecording ? 'not-allowed' : 'pointer',
                        marginLeft: 'auto',
                    }}
                >
                    Discard Draft
                </button>
            </div>

            {error && (
                <div style={{ marginBottom: '0.75rem', padding: '0.75rem', background: '#742a2a', borderRadius: '4px', color: '#fee' }}>
                    {error}
                </div>
            )}
            {saveMessage && (
                <div style={{ marginBottom: '0.75rem', padding: '0.75rem', background: '#22543d', borderRadius: '4px', color: '#e6fffa' }}>
                    {saveMessage}
                </div>
            )}

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.3fr', gap: '1.5rem' }}>
                {/* Transcript Panel */}
                <div style={{ border: '1px solid #333', borderRadius: '6px', padding: '0.75rem', background: '#111' }}>
                    <h4 style={{ marginTop: 0 }}>Transcript (what you said)</h4>
                    {transcript ? (
                        <pre
                            style={{
                                maxHeight: '260px',
                                overflowY: 'auto',
                                whiteSpace: 'pre-wrap',
                                wordWrap: 'break-word',
                                fontFamily: 'SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace',
                                fontSize: '0.85rem',
                                padding: '0.5rem',
                                background: '#0b0b0b',
                            }}
                        >
                            {transcript}
                        </pre>
                    ) : (
                        <p style={{ color: '#666', fontSize: '0.9rem' }}>
                            Здесь в реальном времени будет появляться текст твоего голосового описания во время записи.
                        </p>
                    )}
                </div>

                {/* Rules Preview Panel */}
                <div style={{ border: '1px solid #333', borderRadius: '6px', padding: '0.75rem', background: '#111' }}>
                    <h4 style={{ marginTop: 0 }}>Draft Rules from OpenAI</h4>
                    {rules.length === 0 ? (
                        <p style={{ color: '#666', fontSize: '0.9rem' }}>
                            После обработки аудио здесь появится список сгенерированных правил.
                        </p>
                    ) : (
                        <>
                            <table
                                style={{
                                    width: '100%',
                                    borderCollapse: 'collapse',
                                    marginBottom: '0.75rem',
                                    fontSize: '0.85rem',
                                }}
                            >
                                <thead>
                                    <tr style={{ borderBottom: '1px solid #444' }}>
                                        <th style={{ padding: '0.4rem', textAlign: 'left' }}>Save</th>
                                        <th style={{ padding: '0.4rem', textAlign: 'left' }}>Title</th>
                                        <th style={{ padding: '0.4rem', textAlign: 'left' }}>Scope</th>
                                        <th style={{ padding: '0.4rem', textAlign: 'left' }}>Type</th>
                                        <th style={{ padding: '0.4rem', textAlign: 'center' }}>Priority</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {rules.map((rule, idx) => (
                                        <tr key={idx} style={{ borderBottom: '1px solid #333' }}>
                                            <td style={{ padding: '0.4rem', textAlign: 'center' }}>
                                                <input
                                                    type="checkbox"
                                                    checked={rule.selected}
                                                    onChange={() => toggleRuleSelected(idx)}
                                                />
                                            </td>
                                            <td style={{ padding: '0.4rem' }}>{rule.title}</td>
                                            <td style={{ padding: '0.4rem' }}>{rule.scope}</td>
                                            <td style={{ padding: '0.4rem' }}>{rule.type}</td>
                                            <td style={{ padding: '0.4rem', textAlign: 'center' }}>{rule.priority}</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>

                            {/* Details for first rule or all, simple version */}
                            <div
                                style={{
                                    maxHeight: '220px',
                                    overflowY: 'auto',
                                    borderTop: '1px solid #444',
                                    paddingTop: '0.5rem',
                                }}
                            >
                                {rules.map((rule, idx) => (
                                    <div
                                        key={idx}
                                        style={{
                                            marginBottom: '0.75rem',
                                            padding: '0.5rem',
                                            borderRadius: '4px',
                                            background: '#181818',
                                        }}
                                    >
                                        <div
                                            style={{
                                                display: 'flex',
                                                justifyContent: 'space-between',
                                                marginBottom: '0.25rem',
                                            }}
                                        >
                                            <strong>{rule.title}</strong>
                                            <span style={{ fontSize: '0.75rem', color: '#aaa' }}>
                                                {rule.scope} · {rule.type} · prio {rule.priority}
                                            </span>
                                        </div>
                                        <p style={{ fontSize: '0.85rem', color: '#ddd' }}>{rule.description}</p>
                                        {rule.trigger_condition && (
                                            <div style={{ marginTop: '0.25rem' }}>
                                                <strong style={{ fontSize: '0.8rem' }}>Trigger:</strong>
                                                <pre
                                                    style={{
                                                        background: '#0b0b0b',
                                                        padding: '0.4rem',
                                                        borderRadius: '3px',
                                                        fontSize: '0.8rem',
                                                        whiteSpace: 'pre-wrap',
                                                        wordWrap: 'break-word',
                                                    }}
                                                >
                                                    {prettyJson(rule.trigger_condition)}
                                                </pre>
                                            </div>
                                        )}
                                        {rule.action && (
                                            <div style={{ marginTop: '0.25rem' }}>
                                                <strong style={{ fontSize: '0.8rem' }}>Action:</strong>
                                                <pre
                                                    style={{
                                                        background: '#0b0b0b',
                                                        padding: '0.4rem',
                                                        borderRadius: '3px',
                                                        fontSize: '0.8rem',
                                                        whiteSpace: 'pre-wrap',
                                                        wordWrap: 'break-word',
                                                    }}
                                                >
                                                    {prettyJson(rule.action)}
                                                </pre>
                                            </div>
                                        )}
                                    </div>
                                ))}
                            </div>

                            <div style={{ marginTop: '0.5rem', display: 'flex', justifyContent: 'flex-end', gap: '0.75rem' }}>
                                <button
                                    onClick={saveSelectedRules}
                                    disabled={saving || rules.length === 0}
                                    style={{
                                        padding: '0.6rem 1.4rem',
                                        borderRadius: '6px',
                                        border: 'none',
                                        backgroundColor:
                                            saving || rules.length === 0 ? '#444' : '#3182ce',
                                        color: 'white',
                                        cursor:
                                            saving || rules.length === 0
                                                ? 'not-allowed'
                                                : 'pointer',
                                        fontWeight: 600,
                                    }}
                                >
                                    {saving ? 'Saving...' : 'Save Selected Rules'}
                                </button>
                            </div>
                        </>
                    )}
                </div>
            </div>
        </div>
    );
}
