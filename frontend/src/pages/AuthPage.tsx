import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { useNavigate } from 'react-router-dom';

export default function AuthPage() {
    const { login, register } = useAuth();
    const navigate = useNavigate();
    const [isLogin, setIsLogin] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [fullName, setFullName] = useState('');
    const [confirmPassword, setConfirmPassword] = useState('');

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError(null);

        try {
            if (isLogin) {
                await login({ email, password });
            } else {
                if (password !== confirmPassword) {
                    setError("Passwords do not match");
                    return;
                }
                await register({ email, password, full_name: fullName });
            }
            navigate('/');
        } catch (err: any) {
            setError(err.message || "Authentication failed");
        }
    };

    return (
        <div style={{ maxWidth: '400px', margin: '0 auto' }}>
            <div className="card">
                <h2>{isLogin ? 'Log In' : 'Sign Up'}</h2>

                <div style={{ marginBottom: '20px' }}>
                    <button
                        onClick={() => setIsLogin(true)}
                        style={{ marginRight: '10px', opacity: isLogin ? 1 : 0.5 }}
                    >
                        Log In
                    </button>
                    <button
                        onClick={() => setIsLogin(false)}
                        style={{ opacity: !isLogin ? 1 : 0.5 }}
                    >
                        Sign Up
                    </button>
                </div>

                <form onSubmit={handleSubmit}>
                    {!isLogin && (
                        <div>
                            <label>Full Name</label>
                            <input
                                type="text"
                                value={fullName}
                                onChange={e => setFullName(e.target.value)}
                                placeholder="John Doe"
                            />
                        </div>
                    )}

                    <div>
                        <label>Email</label>
                        <input
                            type="email"
                            value={email}
                            onChange={e => setEmail(e.target.value)}
                            required
                            placeholder="email@example.com"
                        />
                    </div>

                    <div>
                        <label>Password</label>
                        <input
                            type="password"
                            value={password}
                            onChange={e => setPassword(e.target.value)}
                            required
                            placeholder="********"
                            minLength={8}
                        />
                    </div>

                    {!isLogin && (
                        <div>
                            <label>Confirm Password</label>
                            <input
                                type="password"
                                value={confirmPassword}
                                onChange={e => setConfirmPassword(e.target.value)}
                                required
                                placeholder="********"
                            />
                        </div>
                    )}

                    {error && <div style={{ color: 'red', marginBottom: '10px' }}>{error}</div>}

                    <button type="submit" style={{ width: '100%', marginTop: '10px' }}>
                        {isLogin ? 'Log In' : 'Sign Up'}
                    </button>
                </form>
            </div>
        </div>
    );
}
