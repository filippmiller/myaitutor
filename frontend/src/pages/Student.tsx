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
    const [lastUserText, setLastUserText] = useState('');
    const [lastAssistantText, setLastAssistantText] = useState('');
    const [audioUrl, setAudioUrl] = useState<string | null>(null);
    const [loading, setLoading] = useState(false);

    const [progress, setProgress] = useState<ProgressResponse | null>(null);
    const [activeTab, setActiveTab] = useState<'chat' | 'progress'>('chat');

    const { logout } = useAuth();
    const navigate = useNavigate();

    const mediaRecorderRef = useRef<MediaRecorder | null>(null);
    const chunksRef = useRef<Blob[]>([]);

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

    const startRecording = async () => {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            const mediaRecorder = new MediaRecorder(stream);
            mediaRecorderRef.current = mediaRecorder;
            chunksRef.current = [];

            mediaRecorder.ondataavailable = (e) => {
                if (e.data.size > 0) chunksRef.current.push(e.data);
            };

            mediaRecorder.onstop = async () => {
                const blob = new Blob(chunksRef.current, { type: 'audio/webm' });
                await sendAudio(blob);
                stream.getTracks().forEach(track => track.stop());
            };

            mediaRecorder.start();
            setIsRecording(true);
        } catch (err) {
            console.error('Error accessing microphone:', err);
            alert('Could not access microphone');
        }
    };

    const stopRecording = () => {
        if (mediaRecorderRef.current && isRecording) {
            mediaRecorderRef.current.stop();
            setIsRecording(false);
        }
    };

    const sendAudio = async (blob: Blob) => {
        setLoading(true);
        const formData = new FormData();
        formData.append('audio_file', blob, 'voice.webm');

        try {
            const res = await fetch('/api/voice_chat', {
                method: 'POST',
                body: formData
            });

            if (await handleAuthError(res)) return;

            if (!res.ok) {
                const err = await res.json();
                alert('Error: ' + err.detail);
                return;
            }

            const data = await res.json();
            setLastUserText(data.user_text);
            setLastAssistantText(data.assistant_text);
            setAudioUrl(data.audio_url);

            // Refresh progress
            progressApi.getProgress().then(setProgress);
        } catch (e) {
            console.error(e);
            alert('Error sending audio');
        } finally {
            setLoading(false);
        }
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
                        <h2>Voice Chat</h2>
                        <button
                            onMouseDown={startRecording}
                            onMouseUp={stopRecording}
                            onTouchStart={startRecording}
                            onTouchEnd={stopRecording}
                            style={{
                                backgroundColor: isRecording ? 'red' : '#1a1a1a',
                                fontSize: '1.2em',
                                width: '100%',
                                marginBottom: '20px'
                            }}
                        >
                            {isRecording ? 'Listening... (Release to send)' : 'Hold to Speak'}
                        </button>

                        {loading && <p>Thinking...</p>}

                        {(lastUserText || lastAssistantText) && (
                            <div className="chat-box">
                                <p><strong>You:</strong> {lastUserText}</p>
                                <hr style={{ borderColor: '#444' }} />
                                <p><strong>Tutor:</strong> {lastAssistantText}</p>

                                {audioUrl && (
                                    <div style={{ marginTop: '10px' }}>
                                        <audio controls src={audioUrl} autoPlay style={{ width: '100%' }} />
                                    </div>
                                )}
                            </div>
                        )}
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
