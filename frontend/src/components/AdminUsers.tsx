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

    useEffect(() => {
        fetchUsers();
    }, []);

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
                <div style={{ padding: '1rem', border: '1px solid #ccc', borderRadius: '4px', background: '#2a2a2a' }}>
                    <h4>User Details: {selectedUser.account.email}</h4>
                    <p><strong>Level:</strong> {selectedUser.profile?.english_level}</p>
                    <p><strong>Preferences:</strong> {selectedUser.profile?.preferences}</p>
                    <button onClick={() => setSelectedUser(null)}>Close</button>
                </div>
            )}
        </div>
    );
}
