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
    const [connectionStatus, setConnectionStatus] = useState('Disconnected');
    const [transcript, setTranscript] = useState<Array<{ role: string, text: string }>>([]);

    const [progress, setProgress] = useState<ProgressResponse | null>(null);
    const [activeTab, setActiveTab] = useState<'chat' | 'progress'>('chat');

    const { logout } = useAuth();
    const navigate = useNavigate();

    const mediaRecorderRef = useRef<MediaRecorder | null>(null);
    const wsRef = useRef<WebSocket | null>(null);
    const chatEndRef = useRef<HTMLDivElement | null>(null);

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

    const startLesson = async () => {
        try {
            // 1. Get Microphone Access
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

            // 2. Connect WebSocket (Cookies will be sent automatically)
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/api/voice-lesson/ws`;
            const ws = new WebSocket(wsUrl);
            wsRef.current = ws;

            setConnectionStatus('Connecting...');

            ws.onopen = () => {
                setConnectionStatus('Connected');
                setIsRecording(true);

                // 3. Start MediaRecorder
                const mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
                mediaRecorderRef.current = mediaRecorder;

                mediaRecorder.ondataavailable = (e) => {
                    if (e.data.size > 0 && ws.readyState === WebSocket.OPEN) {
                        ws.send(e.data);
                    }
                };

                mediaRecorder.start(250); // Send chunks every 250ms
            };

            ws.onmessage = async (event) => {
                if (typeof event.data === 'string') {
                    // Text message (Transcript)
                    const msg = JSON.parse(event.data);
                    if (msg.type === 'transcript') {
                        setTranscript(prev => [...prev, { role: msg.role, text: msg.text }]);
                    }
                } else {
                    // Binary message (Audio)
                    const audioBlob = new Blob([event.data], { type: 'audio/mp3' });
                    const audioUrl = URL.createObjectURL(audioBlob);
                    const audio = new Audio(audioUrl);
                    audio.play();
                }
            };

            ws.onclose = () => {
                setConnectionStatus('Disconnected');
                setIsRecording(false);
                stopMediaRecorder();
            };

            ws.onerror = (e) => {
                console.error("WebSocket error:", e);
                setConnectionStatus('Error');
            };

        } catch (err) {
            console.error('Error accessing microphone:', err);
            alert('Could not access microphone');
        }
    };

    const stopMediaRecorder = () => {
        if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
            mediaRecorderRef.current.stop();
            mediaRecorderRef.current.stream.getTracks().forEach(track => track.stop());
        }
    };

    const stopLesson = () => {
        if (wsRef.current) {
            wsRef.current.close();
        }
        stopMediaRecorder();
        setIsRecording(false);
        setConnectionStatus('Disconnected');
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

                        {!isRecording ? (
                            <button
                                onClick={startLesson}
                                style={{
                                    backgroundColor: '#4CAF50',
                                    fontSize: '1.2em',
                                    width: '100%',
                                    marginBottom: '20px',
                                    padding: '15px'
                                }}
                            >
                                Start Live Lesson
                            </button>
                        ) : (
                            <button
                                onClick={stopLesson}
                                style={{
                                    backgroundColor: '#f44336',
                                    fontSize: '1.2em',
                                    width: '100%',
                                    marginBottom: '20px',
                                    padding: '15px'
                                }}
                            >
                                End Lesson
                            </button>
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
                                    <strong>{t.role === 'user' ? 'You' : 'Tutor'}:</strong> {t.text}
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
