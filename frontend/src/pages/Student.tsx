import { useState, useEffect, useRef } from 'react';
import { useAuth } from '../context/AuthContext';
import { useNavigate } from 'react-router-dom';
import { progressApi, ProgressResponse } from '../api/progress';

interface UserProfile {
    id?: number;
    name: string;
    english_level: string;
    goals: string;
    pains: string;
}



export default function Student() {
    const [profile, setProfile] = useState<UserProfile>({
        name: '',
        english_level: 'A1',
        goals: '',
        pains: ''
    });
    const [isRecording, setIsRecording] = useState(false);
    const [connectionStatus, setConnectionStatus] = useState<'Disconnected' | 'Connecting...' | 'Connected' | 'Paused' | 'Error'>('Disconnected');
    const [transcript, setTranscript] = useState<Array<{ role: string, text: string, final?: boolean }>>([]);
    const [sttLanguage, setSttLanguage] = useState<'ru-RU' | 'en-US'>('ru-RU');

    const [progress, setProgress] = useState<ProgressResponse | null>(null);
    const [activeTab, setActiveTab] = useState<'chat' | 'progress'>('chat');

    const { logout } = useAuth();
    const navigate = useNavigate();

    const mediaRecorderRef = useRef<MediaRecorder | null>(null);
    const wsRef = useRef<WebSocket | null>(null);
    const lessonSessionIdRef = useRef<number | null>(null);
    const chatEndRef = useRef<HTMLDivElement | null>(null);
    const audioContextRef = useRef<AudioContext | null>(null);

    // Audio Queue Management
    const audioQueueRef = useRef<Blob[]>([]);
    const isPlayingRef = useRef(false);
    const currentSourceRef = useRef<AudioBufferSourceNode | null>(null);

    const handleAuthError = async (res: Response) => {
        if (res.status === 401) {
            await logout();
            navigate('/auth');
            return true;
        }
        return false;
    };

    useEffect(() => {
        fetch('/api/profile')
            .then(async res => {
                if (await handleAuthError(res)) return null;
                return res.json();
            })
            .then(data => {
                if (data) setProfile(data);
            });

        progressApi.getProgress()
            .then(data => setProgress(data))
            .catch(async err => {
                if (err.status === 401) {
                    await logout();
                    navigate('/auth');
                }
            });
    }, []);

    useEffect(() => {
        chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [transcript]);

    const saveProfile = async () => {
        const params = new URLSearchParams();
        params.append('name', profile.name);
        params.append('english_level', profile.english_level);
        params.append('goals', profile.goals);
        params.append('pains', profile.pains);

        const res = await fetch('/api/profile?' + params.toString(), {
            method: 'POST'
        });

        if (await handleAuthError(res)) return;

        const data = await res.json();
        setProfile(data);
        alert('Profile saved!');
    };

    const startLesson = async (isResume: boolean) => {
        console.log('🚀 [START LESSON] Initiating...');
        try {
            // 1. Get Microphone Access
            console.log('🎤 [MICROPHONE] Requesting access...');
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            console.log('✅ [MICROPHONE] Access granted');

            // 2. Initialize Audio Context
            if (!audioContextRef.current) {
                audioContextRef.current = new (window.AudioContext || (window as any).webkitAudioContext)();
            }

            // 3. Connect WebSocket
            const isDev = window.location.hostname === 'localhost';
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            let wsUrl = isDev
                ? 'ws://localhost:8000/api/ws/voice'
                : `${protocol}//${window.location.host}/api/ws/voice`;

            if (isResume && lessonSessionIdRef.current) {
                const params = new URLSearchParams({
                    lesson_session_id: String(lessonSessionIdRef.current),
                    resume: '1',
                });
                wsUrl += `?${params.toString()}`;
            }
            console.log(`🔌 [WEBSOCKET] Creating connection to: ${wsUrl}`);
            const ws = new WebSocket(wsUrl);
            wsRef.current = ws;

            setConnectionStatus('Connecting...');
            console.log('⏳ [STATE] Connection status: Connecting...');

            ws.onopen = () => {
                console.log('✅ [WEBSOCKET] Connection OPENED');
                setConnectionStatus('Connected');
                setIsRecording(true);
                console.log('🎙️ [STATE] Connection status: Connected, Recording started');

                // Send config and start event
                ws.send(JSON.stringify({ type: 'config', stt_language: sttLanguage }));
                ws.send(JSON.stringify({ type: 'system_event', event: 'lesson_started' }));

                // 4. Start MediaRecorder
                const mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
                mediaRecorderRef.current = mediaRecorder;
                console.log('🎬 [RECORDER] MediaRecorder created');

                mediaRecorder.ondataavailable = (e) => {
                    if (e.data.size > 0 && ws.readyState === WebSocket.OPEN) {
                        console.log(`📤 [AUDIO] Sending chunk: ${e.data.size} bytes`);
                        ws.send(e.data);
                    }
                };

                mediaRecorder.start(250); // Send chunks every 250ms
                console.log('▶️ [RECORDER] Started (250ms chunks)');
            };

            ws.onmessage = async (event) => {
                if (event.data instanceof Blob) {
                    // Binary message = Audio
                    console.log(`🔊 [AUDIO] Received ${event.data.size} bytes`);
                    queueAudio(event.data);
                } else {
                    // Text message = JSON
                    try {
                        const msg = JSON.parse(event.data);
                        console.log('📨 [WEBSOCKET] Received:', msg);

                        if (msg.type === 'lesson_info') {
                            // Backend tells us which logical LessonSession this WS belongs to (for pause/resume)
                            if (typeof msg.lesson_session_id === 'number') {
                                lessonSessionIdRef.current = msg.lesson_session_id;
                                console.log('📚 [LESSON] lesson_session_id =', msg.lesson_session_id);
                            }
                        } else if (msg.type === 'transcript') {
                            console.log(`💬 [TRANSCRIPT] ${msg.role}: ${msg.text}`);

                            // If user spoke, stop any current AI speech immediately
                            if (msg.role === 'user') {
                                console.log('🛑 [AUDIO] User spoke, stopping AI playback');
                                stopAudioPlayback();
                            }

                            setTranscript(prev => {
                                const last = prev[prev.length - 1];
                                // Only merge if this is a streaming fragment (no "final" flag) AND last message was assistant
                                if (last && last.role === 'assistant' && msg.role === 'assistant' && !msg.final) {
                                    const newPrev = [...prev];
                                    // Add a space if needed
                                    const separator = last.text.endsWith(' ') ? '' : ' ';
                                    newPrev[prev.length - 1] = { ...last, text: last.text + separator + msg.text };
                                    return newPrev;
                                }
                                // Don't add empty final markers to transcript
                                if (msg.final && !msg.text) {
                                    return prev;
                                }
                                return [...prev, { role: msg.role, text: msg.text }];
                            });
                        } else if (msg.type === 'system') {
                            console.log(`[SYSTEM] ${msg.level}: ${msg.message}`);
                            if (msg.level === 'error') {
                                alert(`Error: ${msg.message}`);
                                setConnectionStatus('Error');
                            } else if (msg.level === 'info' && msg.message === 'Lesson paused.') {
                                // Server confirmed pause; keep WS open until it closes, UI already stopped mic/audio.
                                setConnectionStatus('Paused');
                                if (msg.resume_hint) {
                                    console.log('📝 [PAUSE SUMMARY]', msg.resume_hint);
                                }
                            }
                        }
                    } catch (e) {
                        console.error('❌ [WEBSOCKET] Failed to parse message:', event.data);
                    }
                }
            };

            ws.onclose = (event) => {
                console.log(`❌ [WEBSOCKET] Connection CLOSED - Code: ${event.code}, Reason: ${event.reason || 'No reason provided'}, Clean: ${event.wasClean}`);

                if (event.code === 1000 && event.reason === 'lesson_paused') {
                    // Graceful pause initiated by server
                    setConnectionStatus('Paused');
                } else {
                    let statusMsg: typeof connectionStatus = 'Disconnected';
                    if (event.code !== 1000 && event.code !== 1001 && event.code !== 1005) {
                        statusMsg = 'Error';
                        // Also show alert for visibility
                        if (event.reason) {
                            alert(`Connection closed: ${event.reason}`);
                        }
                    }
                    setConnectionStatus(statusMsg);
                }

                setIsRecording(false);
                stopMediaRecorder();
                console.log('🛑 [STATE] Connection closed, Recording stopped');
            };

            ws.onerror = (e) => {
                console.error("💥 [WEBSOCKET] ERROR:", e);
                setConnectionStatus('Error');
                console.log('⚠️ [STATE] Connection status: Error');
            };

        } catch (err) {
            console.error('💥 [ERROR] Failed to start lesson:', err);
            alert('Could not access microphone');
        }
    };

    const stopMediaRecorder = () => {
        if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
            mediaRecorderRef.current.stop();
            mediaRecorderRef.current.stream.getTracks().forEach(track => track.stop());
        }
    };

    const pauseLesson = () => {
        console.log('⏸️ [LESSON] Pause requested');
        if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
            wsRef.current.send(JSON.stringify({ type: 'system_event', event: 'lesson_paused' }));
        }
        stopMediaRecorder();
        stopAudioPlayback();
        setIsRecording(false);
        // Actual status will be set to 'Paused' when server confirms or closes with reason
    };

    const stopLesson = () => {
        console.log('🟥 [LESSON] End requested');
        if (wsRef.current) {
            try {
                wsRef.current.close();
            } catch (e) {
                // ignore
            }
        }
        stopMediaRecorder();
        stopAudioPlayback();
        lessonSessionIdRef.current = null;
        setIsRecording(false);
        setConnectionStatus('Disconnected');
    };

    const stopAudioPlayback = () => {
        if (currentSourceRef.current) {
            try {
                currentSourceRef.current.stop();
            } catch (e) {
                // ignore
            }
            currentSourceRef.current = null;
        }
        audioQueueRef.current = [];
        isPlayingRef.current = false;
    };

    const queueAudio = (blob: Blob) => {
        audioQueueRef.current.push(blob);
        playNextInQueue();
    };

    const playNextInQueue = async () => {
        if (isPlayingRef.current || audioQueueRef.current.length === 0) return;

        isPlayingRef.current = true;
        const blob = audioQueueRef.current.shift();

        if (!blob) {
            isPlayingRef.current = false;
            return;
        }

        if (!audioContextRef.current) {
            audioContextRef.current = new (window.AudioContext || (window as any).webkitAudioContext)();
        }

        try {
            const arrayBuffer = await blob.arrayBuffer();
            const audioBuffer = await audioContextRef.current.decodeAudioData(arrayBuffer);
            const source = audioContextRef.current.createBufferSource();
            source.buffer = audioBuffer;
            source.connect(audioContextRef.current.destination);

            source.onended = () => {
                isPlayingRef.current = false;
                playNextInQueue();
            };

            currentSourceRef.current = source;
            source.start(0);
        } catch (e) {
            console.error('❌ [AUDIO] Playback failed:', e);
            isPlayingRef.current = false;
            playNextInQueue();
        }
    };

    const renderMessageText = (t: { role: string; text: string }) => {
        // For assistant messages, split long text into sentence-like chunks for readability.
        if (t.role === 'assistant') {
            // Split on sentence-ending punctuation followed by whitespace.
            const parts = t.text.split(/(?<=[\.\!\?])\s+/);
            return parts.map((part, idx) => (
                <span key={idx}>
                    {idx > 0 && <><br /><br /></>}
                    {part}
                </span>
            ));
        }
        // For user messages, render as-is.
        return t.text;
    };

    return (
        <div>
            <div style={{ marginBottom: '1rem' }}>
                <button
                    onClick={() => setActiveTab('chat')}
                    style={{
                        marginRight: '1rem',
                        backgroundColor: activeTab === 'chat' ? '#646cff' : '#333'
                    }}
                >
                    Chat
                </button>
                <button
                    onClick={() => setActiveTab('progress')}
                    style={{
                        backgroundColor: activeTab === 'progress' ? '#646cff' : '#333'
                    }}
                >
                    Progress
                </button>
            </div>

            {activeTab === 'chat' ? (
                <>
                    <div className="card">
                        <h2>Student Profile</h2>
                        <input
                            placeholder="Name"
                            value={profile.name}
                            onChange={e => setProfile({ ...profile, name: e.target.value })}
                        />
                        <select
                            value={profile.english_level}
                            onChange={e => setProfile({ ...profile, english_level: e.target.value })}
                        >
                            <option value="A1">A1</option>
                            <option value="A2">A2</option>
                            <option value="B1">B1</option>
                            <option value="B2">B2</option>
                            <option value="C1">C1</option>
                        </select>
                        <textarea
                            placeholder="Goals (e.g. speak fluently)"
                            value={profile.goals}
                            onChange={e => setProfile({ ...profile, goals: e.target.value })}
                        />
                        <textarea
                            placeholder="Pains (e.g. fear of speaking)"
                            value={profile.pains}
                            onChange={e => setProfile({ ...profile, pains: e.target.value })}
                        />
                        <button onClick={saveProfile}>Save Profile</button>
                    </div>

                    <div className="card">
                        <h2>Voice Lesson</h2>

                        <div style={{ marginBottom: '15px' }}>
                            <label style={{ marginRight: '10px' }}>Language:</label>
                            <select
                                value={sttLanguage}
                                onChange={(e) => setSttLanguage(e.target.value as 'ru-RU' | 'en-US')}
                                disabled={isRecording}
                                style={{ padding: '5px' }}
                            >
                                <option value="ru-RU">Russian (ru-RU)</option>
                                <option value="en-US">English (en-US)</option>
                            </select>
                        </div>

                        {!isRecording ? (
                            <button
                                onClick={() => {
                                    if (connectionStatus === 'Paused' && lessonSessionIdRef.current) {
                                        // Resume existing lesson
                                        startLesson(true);
                                    } else {
                                        // Start new lesson
                                        lessonSessionIdRef.current = null;
                                        startLesson(false);
                                    }
                                }}
                                style={{
                                    backgroundColor: '#4CAF50',
                                    fontSize: '1.2em',
                                    width: '100%',
                                    marginBottom: '20px',
                                    padding: '15px'
                                }}
                            >
                                {connectionStatus === 'Paused' && lessonSessionIdRef.current
                                    ? 'Resume Lesson'
                                    : 'Start Live Lesson'}
                            </button>
                        ) : (
                            <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '20px' }}>
                                <button
                                    onClick={pauseLesson}
                                    style={{
                                        backgroundColor: '#ff9800',
                                        fontSize: '1.1em',
                                        flex: 1,
                                        padding: '15px',
                                    }}
                                >
                                    Pause Lesson
                                </button>
                                <button
                                    onClick={stopLesson}
                                    style={{
                                        backgroundColor: '#f44336',
                                        fontSize: '1.1em',
                                        flex: 1,
                                        padding: '15px',
                                    }}
                                >
                                    End Lesson
                                </button>
                            </div>
                        )}

                        <div className="status-indicator" style={{ marginBottom: '10px', color: '#888' }}>
                            Status: {connectionStatus}
                        </div>

                        <div className="chat-box" style={{ maxHeight: '400px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '10px' }}>
                            {transcript.map((t, i) => (
                                <div key={i} style={{
                                    alignSelf: t.role === 'user' ? 'flex-end' : 'flex-start',
                                    backgroundColor: t.role === 'user' ? '#2a2a2a' : '#1a3a5a',
                                    padding: '10px',
                                    borderRadius: '8px',
                                    maxWidth: '80%'
                                }}>
                                    <strong>{t.role === 'user' ? 'You' : 'Tutor'}:</strong>{' '}
                                    {renderMessageText(t)}
                                </div>
                            ))}
                            <div ref={chatEndRef} />
                        </div>
                    </div>
                </>
            ) : (
                <div className="card">
                    <h2>Your Progress</h2>
                    {progress ? (
                        <div>
                            <div style={{ display: 'flex', gap: '2rem', marginBottom: '2rem' }}>
                                <div>
                                    <h3>Stats</h3>
                                    <p>Sessions: {progress.state.session_count}</p>
                                    <p>Messages: {progress.state.total_messages}</p>
                                    <p>XP: {progress.state.xp_points}</p>
                                    <p>Last Session: {progress.state.last_session_at ? new Date(progress.state.last_session_at).toLocaleString() : 'Never'}</p>
                                </div>
                                <div>
                                    <h3>Weak Words</h3>
                                    <ul>
                                        {progress.state.weak_words.length > 0 ? (
                                            progress.state.weak_words.map((w, i) => <li key={i}>{w}</li>)
                                        ) : (
                                            <li>None yet</li>
                                        )}
                                    </ul>
                                </div>
                                <div>
                                    <h3>Known Words</h3>
                                    <ul>
                                        {progress.state.known_words.length > 0 ? (
                                            progress.state.known_words.slice(0, 10).map((w, i) => <li key={i}>{w}</li>)
                                        ) : (
                                            <li>None yet</li>
                                        )}
                                    </ul>
                                </div>
                            </div>

                            <h3>Recent Sessions</h3>
                            {progress.recent_sessions.length > 0 ? (
                                <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                                    {progress.recent_sessions.map(session => (
                                        <div key={session.id} style={{ border: '1px solid #444', padding: '1rem', borderRadius: '8px' }}>
                                            <p style={{ fontSize: '0.9em', color: '#888' }}>{new Date(session.created_at).toLocaleString()}</p>
                                            <p><strong>Summary:</strong> {session.summary_text || 'No summary'}</p>
                                            {session.practiced_words.length > 0 && (
                                                <p style={{ fontSize: '0.9em' }}>Practiced: {session.practiced_words.join(', ')}</p>
                                            )}
                                        </div>
                                    ))}
                                </div>
                            ) : (
                                <p>No sessions yet.</p>
                            )}
                        </div>
                    ) : (
                        <p>Loading progress...</p>
                    )}
                </div>
            )}
        </div>
    );
}
