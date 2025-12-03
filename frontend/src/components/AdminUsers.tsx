import { useState, useEffect } from 'react';

interface User {
    id: number;
    email: string;
    full_name: string;
    role: string;
    is_active: boolean;
    created_at: string;
}

interface UserProfile {
    id: number;
    name: string;
    english_level: string;
    preferences: string;
    preferred_tts_engine?: string;
    preferred_stt_engine?: string;
    preferred_voice_id?: string;
    minutes_balance?: number;
}

interface Voice {
    id: string;
    name: string;
    gender: string;
}

interface VoicesResponse {
    openai: Voice[];
    yandex: Voice[];
}

export default function AdminUsers() {
    const [users, setUsers] = useState<User[]>([]);
    const [selectedUser, setSelectedUser] = useState<{ account: User, profile: UserProfile } | null>(null);
    const [loading, setLoading] = useState(false);
    const [voices, setVoices] = useState<VoicesResponse>({ openai: [], yandex: [] });

    // Voice Settings State
    const [ttsEngine, setTtsEngine] = useState('openai');
    const [voiceId, setVoiceId] = useState('alloy');
    const [testingVoice, setTestingVoice] = useState(false);
    const [sampleText, setSampleText] = useState('Hello, this is a test of the selected voice.');

    useEffect(() => {
        fetchUsers();
        fetchVoices();
    }, []);

    useEffect(() => {
        if (selectedUser && selectedUser.profile) {
            setTtsEngine(selectedUser.profile.preferred_tts_engine || 'openai');
            setVoiceId(selectedUser.profile.preferred_voice_id || 'alloy');
        }
    }, [selectedUser]);

    const fetchUsers = async () => {
        setLoading(true);
        try {
            const res = await fetch('/api/admin/users');
            if (res.ok) {
                const data = await res.json();
                setUsers(data);
            }
        } catch (e) {
            console.error(e);
        } finally {
            setLoading(false);
        }
    };

    const fetchVoices = async () => {
        try {
            const res = await fetch('/api/admin/voices');
            if (res.ok) {
                const data = await res.json();
                setVoices(data);
            }
        } catch (e) {
            console.error(e);
        }
    };

    const fetchUserDetails = async (id: number) => {
        try {
            const res = await fetch(`/api/admin/users/${id}`);
            if (res.ok) {
                const data = await res.json();
                console.log("User details:", data);
                setSelectedUser(data);
            } else {
                const err = await res.json();
                alert(`Error fetching user details: ${err.detail || res.statusText}`);
            }
        } catch (e) {
            console.error(e);
            alert(`Error fetching user details: ${e}`);
        }
    };

    const handleSaveVoice = async () => {
        if (!selectedUser) return;
        try {
            const res = await fetch(`/api/admin/users/${selectedUser.account.id}/voice`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    preferred_tts_engine: ttsEngine,
                    preferred_stt_engine: ttsEngine, // Sync STT with TTS for now as per prompt "default OpenAI for both"
                    preferred_voice_id: voiceId
                })
            });
            if (res.ok) {
                alert('Voice settings saved!');
                fetchUserDetails(selectedUser.account.id);
            } else {
                const err = await res.json();
                alert(`Error saving voice settings: ${err.detail || res.statusText}`);
            }
        } catch (e) {
            console.error(e);
            alert(`Error saving voice settings: ${e}`);
        }
    };

    const handleTestVoice = async () => {
        setTestingVoice(true);
        try {
            const res = await fetch('/api/admin/voices/test', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    engine: ttsEngine,
                    voice_id: voiceId,
                    text: sampleText
                })
            });
            if (res.ok) {
                const blob = await res.blob();
                const url = window.URL.createObjectURL(blob);
                const audio = new Audio(url);
                audio.play();
            } else {
                const err = await res.json();
                alert(`Failed to generate voice test: ${err.detail || res.statusText}`);
            }
        } catch (e) {
            console.error(e);
            alert(`Error testing voice: ${e}`);
        } finally {
            setTestingVoice(false);
        }
    };

    const availableVoices = ttsEngine === 'openai' ? voices.openai : voices.yandex;

    return (
        <div>
            <h3>Users</h3>
            {loading && <p>Loading...</p>}
            <table style={{ width: '100%', borderCollapse: 'collapse', marginBottom: '20px' }}>
                <thead>
                    <tr style={{ textAlign: 'left', borderBottom: '1px solid #ccc' }}>
                        <th>ID</th>
                        <th>Email</th>
                        <th>Name</th>
                        <th>Role</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    {users.map(user => (
                        <tr key={user.id} style={{ borderBottom: '1px solid #eee' }}>
                            <td>{user.id}</td>
                            <td>{user.email}</td>
                            <td>{user.full_name}</td>
                            <td>{user.role}</td>
                            <td>
                                <button onClick={() => fetchUserDetails(user.id)}>Details</button>
                            </td>
                        </tr>
                    ))}
                </tbody>
            </table>

            {selectedUser && (
                <div style={{ padding: '1rem', border: '1px solid #ccc', borderRadius: '4px', background: '#2a2a2a', marginTop: '20px' }}>
                    <h4>User Details: {selectedUser.account.email}</h4>
                    <p><strong>Level:</strong> {selectedUser.profile?.english_level}</p>
                    <p><strong>Minutes Balance:</strong> {selectedUser.profile?.minutes_balance ?? 0}</p>

                    <div style={{ marginTop: '1rem', padding: '1rem', background: '#333', borderRadius: '4px' }}>
                        <h5>Voice Settings</h5>

                        <label style={{ display: 'block', marginBottom: '10px' }}>
                            Engine:
                            <select
                                value={ttsEngine}
                                onChange={e => {
                                    setTtsEngine(e.target.value);
                                    // Reset voice ID to first available when engine changes
                                    const newVoices = e.target.value === 'openai' ? voices.openai : voices.yandex;
                                    if (newVoices.length > 0) setVoiceId(newVoices[0].id);
                                }}
                                style={{ marginLeft: '10px' }}
                            >
                                <option value="openai">OpenAI</option>
                                <option value="yandex">Yandex</option>
                            </select>
                        </label>

                        <label style={{ display: 'block', marginBottom: '10px' }}>
                            Voice:
                            <select
                                value={voiceId}
                                onChange={e => setVoiceId(e.target.value)}
                                style={{ marginLeft: '10px' }}
                            >
                                {availableVoices.map(v => (
                                    <option key={v.id} value={v.id}>{v.name} ({v.gender})</option>
                                ))}
                            </select>
                        </label>

                        <label style={{ display: 'block', marginBottom: '10px' }}>
                            Test Text:
                            <input
                                type="text"
                                value={sampleText}
                                onChange={e => setSampleText(e.target.value)}
                                style={{ marginLeft: '10px' }}
                            />
                        </label>

                        <div style={{ display: 'flex', gap: '10px' }}>
                            <button onClick={handleSaveVoice}>Save Voice Settings</button>
                            <button onClick={handleTestVoice} disabled={testingVoice}>
                                {testingVoice ? 'Generating...' : 'Test Voice'}
                            </button>
                        </div>
                    </div>

                    <button onClick={() => setSelectedUser(null)} style={{ marginTop: '10px' }}>Close</button>
                </div>
            )}
        </div>
    );
}
