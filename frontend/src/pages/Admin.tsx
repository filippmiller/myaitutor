import { useState, useEffect } from 'react';
import TokensPanel from '../components/TokensPanel';
import AdminUsers from '../components/AdminUsers';
import AdminRules from '../components/AdminRules';

export default function Admin() {
    const [activeTab, setActiveTab] = useState('settings');
    const [apiKey, setApiKey] = useState('');
    const [model, setModel] = useState('gpt-4o-mini');
    const [msg, setMsg] = useState('');
    const [testResult, setTestResult] = useState('');

    useEffect(() => {
        if (activeTab === 'settings') {
            fetch('/api/admin/settings')
                .then(res => res.json())
                .then(data => {
                    if (data.openai_api_key) setApiKey(data.openai_api_key);
                    if (data.default_model) setModel(data.default_model);
                });
        }
    }, [activeTab]);

    const save = async () => {
        const res = await fetch('/api/admin/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                openai_api_key: apiKey,
                default_model: model
            })
        });
        if (res.ok) setMsg('Saved!');
        else setMsg('Error saving');
    };

    const testOpenAI = async () => {
        setTestResult('Testing OpenAI...');
        try {
            const res = await fetch('/api/admin/test-openai', { method: 'POST' });
            const data = await res.json();
            setTestResult(`OpenAI: ${data.status} - ${data.message}`);
        } catch (e) {
            setTestResult('OpenAI Test Failed');
        }
    };

    return (
        <div className="card">
            <h2>Admin Dashboard</h2>

            <div style={{ display: 'flex', gap: '1rem', marginBottom: '2rem', borderBottom: '1px solid #444' }}>
                <button
                    onClick={() => setActiveTab('settings')}
                    style={{ background: activeTab === 'settings' ? '#444' : 'transparent', border: 'none', color: 'white', padding: '10px' }}
                >
                    Settings
                </button>
                <button
                    onClick={() => setActiveTab('users')}
                    style={{ background: activeTab === 'users' ? '#444' : 'transparent', border: 'none', color: 'white', padding: '10px' }}
                >
                    Users
                </button>
                <button
                    onClick={() => setActiveTab('rules')}
                    style={{ background: activeTab === 'rules' ? '#444' : 'transparent', border: 'none', color: 'white', padding: '10px' }}
                >
                    System Rules
                </button>
            </div>

            {activeTab === 'settings' && (
                <div>
                    <h3>Global Settings</h3>
                    <div style={{ marginBottom: '20px' }}>
                        <h4>OpenAI</h4>
                        <label style={{ display: 'block', marginBottom: '10px' }}>
                            API Key:
                            <input
                                type="password"
                                value={apiKey}
                                onChange={e => setApiKey(e.target.value)}
                                placeholder="sk-..."
                                style={{ marginLeft: '10px', width: '300px' }}
                            />
                        </label>
                        <label style={{ display: 'block', marginBottom: '10px' }}>
                            Model:
                            <select value={model} onChange={e => setModel(e.target.value)} style={{ marginLeft: '10px' }}>
                                <option value="gpt-4o-mini">gpt-4o-mini</option>
                                <option value="gpt-4-turbo">gpt-4-turbo</option>
                                <option value="gpt-3.5-turbo">gpt-3.5-turbo</option>
                            </select>
                        </label>
                        <button onClick={testOpenAI} style={{ marginRight: '10px' }}>Test OpenAI</button>
                    </div>

                    <div style={{ marginTop: '20px', borderTop: '1px solid #ccc', paddingTop: '20px' }}>
                        <button onClick={save} style={{ backgroundColor: '#4CAF50', color: 'white', padding: '10px 20px' }}>Save All Settings</button>
                        {msg && <span style={{ marginLeft: '10px', color: 'green' }}>{msg}</span>}
                    </div>

                    {testResult && (
                        <div style={{ marginTop: '20px', padding: '10px', background: '#f0f0f0', borderRadius: '4px', color: '#333' }}>
                            <strong>Test Result:</strong> {testResult}
                        </div>
                    )}

                    <TokensPanel />
                </div>
            )}

            {activeTab === 'users' && <AdminUsers />}
            {activeTab === 'rules' && <AdminRules />}
        </div>
    );
}
