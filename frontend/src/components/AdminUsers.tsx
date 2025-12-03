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
}

export default function AdminUsers() {
    const [users, setUsers] = useState<User[]>([]);
    const [selectedUser, setSelectedUser] = useState<{ account: User, profile: UserProfile } | null>(null);
    const [loading, setLoading] = useState(false);

    // Preference state
    const [prefAddress, setPrefAddress] = useState('');
    const [prefVoice, setPrefVoice] = useState('alloy');
    const [testingVoice, setTestingVoice] = useState(false);

    useEffect(() => {
        fetchUsers();
    }, []);

    useEffect(() => {
        if (selectedUser && selectedUser.profile) {
            try {
                const p = JSON.parse(selectedUser.profile.preferences || '{}');
                setPrefAddress(p.preferred_address || '');
                setPrefVoice(p.preferred_voice || 'alloy');
            } catch (e) {
                setPrefAddress('');
                setPrefVoice('alloy');
            }
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

    const fetchUserDetails = async (id: number) => {
        try {
            const res = await fetch(`/api/admin/users/${id}`);
            if (res.ok) {
                const data = await res.json();
                setSelectedUser(data);
            }
        } catch (e) {
            console.error(e);
        }
    };

    const handleSavePrefs = async () => {
        if (!selectedUser) return;
        try {
            const res = await fetch(`/api/admin/users/${selectedUser.account.id}/preferences`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    preferred_address: prefAddress,
                    preferred_voice: prefVoice
                })
            });
            if (res.ok) {
                alert('Saved!');
                fetchUserDetails(selectedUser.account.id);
            } else {
                alert('Error saving');
            }
        } catch (e) {
            console.error(e);
            alert('Error saving');
        }
    };

    const handleTestVoice = async () => {
        setTestingVoice(true);
        try {
            const res = await fetch('/api/admin/test-voice-gen', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    text: "Hello, this is a test of the selected voice.",
                    voice: prefVoice
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

                    <div style={{ marginTop: '1rem', padding: '1rem', background: '#333', borderRadius: '4px' }}>
                        <h5>Preferences</h5>
                        <label style={{ display: 'block', marginBottom: '10px' }}>
                            Address as:
                            <input
                                type="text"
                                placeholder="e.g. My Lord"
                                value={prefAddress}
                                onChange={e => setPrefAddress(e.target.value)}
                                style={{ marginLeft: '10px' }}
                            />
                        </label>
                        <label style={{ display: 'block', marginBottom: '10px' }}>
                            Voice:
                            <select
                                value={prefVoice}
                                onChange={e => setPrefVoice(e.target.value)}
                                style={{ marginLeft: '10px' }}
                            >
                                <optgroup label="OpenAI">
                                    <option value="alloy">Alloy</option>
                                    <option value="echo">Echo</option>
                                    <option value="fable">Fable</option>
                                    <option value="onyx">Onyx</option>
                                    <option value="nova">Nova</option>
                                    <option value="shimmer">Shimmer</option>
                                </optgroup>
                                <optgroup label="Yandex">
                                    <option value="alisa">Alisa (Yandex)</option>
                                    <option value="alena">Alena (Yandex)</option>
                                    <option value="filipp">Filipp (Yandex)</option>
                                    <option value="jane">Jane (Yandex)</option>
                                    <option value="madirus">Madirus (Yandex)</option>
                                    <option value="omazh">Omazh (Yandex)</option>
                                    <option value="zahar">Zahar (Yandex)</option>
                                    <option value="ermil">Ermil (Yandex)</option>
                                </optgroup>
                            </select>
                        </label>
                        <div style={{ display: 'flex', gap: '10px' }}>
                            <button onClick={handleSavePrefs}>Save Preferences</button>
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
