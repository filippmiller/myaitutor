import { useState, useEffect } from 'react';
import TokensPanel from '../components/TokensPanel';
import AdminUsers from '../components/AdminUsers';
import AdminRules from '../components/AdminRules';
import AdminBilling from '../components/AdminBilling';
import AdminAnalytics from '../components/AdminAnalytics';
import AIChatPanel from '../components/AIChatPanel';
import AdminAIRules from '../components/AdminAIRules';
import AdminBeginnerRules from '../components/AdminBeginnerRules';
import AdminLessonPrompts from '../components/AdminLessonPrompts';

export default function Admin() {
    const [activeTab, setActiveTab] = useState('settings');
    const [apiKey, setApiKey] = useState('');
    const [model, setModel] = useState('gpt-4o-mini');
    const [msg, setMsg] = useState('');
    const [testResult, setTestResult] = useState('');
    const [aiChatOpen, setAiChatOpen] = useState(false);

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

            <div style={{ display: 'flex', gap: '1rem', marginBottom: '2rem', borderBottom: '1px solid #444', overflowX: 'auto', paddingBottom: '5px' }}>
                <button
                    onClick={() => setActiveTab('settings')}
                    style={{ background: activeTab === 'settings' ? '#444' : 'transparent', border: 'none', color: 'white', padding: '10px', whiteSpace: 'nowrap' }}
                >
                    Settings
                </button>
                <button
                    onClick={() => setActiveTab('users')}
                    style={{ background: activeTab === 'users' ? '#444' : 'transparent', border: 'none', color: 'white', padding: '10px', whiteSpace: 'nowrap' }}
                >
                    Users
                </button>
                <button
                    onClick={() => setActiveTab('rules')}
                    style={{ background: activeTab === 'rules' ? '#444' : 'transparent', border: 'none', color: 'white', padding: '10px', whiteSpace: 'nowrap' }}
                >
                    System Rules
                </button>
                <button
                    onClick={() => setActiveTab('ai-rules')}
                    style={{ background: activeTab === 'ai-rules' ? '#444' : 'transparent', border: 'none', color: 'white', padding: '10px', whiteSpace: 'nowrap' }}
                >
                    AI Rules
                </button>
                <button
                    onClick={() => setActiveTab('beginner-rules')}
                    style={{ background: activeTab === 'beginner-rules' ? '#444' : 'transparent', border: 'none', color: 'white', padding: '10px', whiteSpace: 'nowrap' }}
                >
                    Beginner Rules
                </button>
                <button
                    onClick={() => setActiveTab('billing')}
                    style={{ background: activeTab === 'billing' ? '#444' : 'transparent', border: 'none', color: 'white', padding: '10px', whiteSpace: 'nowrap' }}
                >
                    Billing
                </button>
                <button
                    onClick={() => setActiveTab('analytics')}
                    style={{ background: activeTab === 'analytics' ? '#444' : 'transparent', border: 'none', color: 'white', padding: '10px', whiteSpace: 'nowrap' }}
                >
                    Analytics
                </button>
                <button
                    onClick={() => setActiveTab('lesson-prompts')}
                    style={{ background: activeTab === 'lesson-prompts' ? '#444' : 'transparent', border: 'none', color: 'white', padding: '10px', whiteSpace: 'nowrap' }}
                >
                    Lesson Prompts
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
                        <button onClick={async () => {
                            setTestResult('Testing FFmpeg...');
                            try {
                                const res = await fetch('/api/admin/test-ffmpeg', { method: 'POST' });
                                const data = await res.json();
                                setTestResult(`FFmpeg: ${data.status} - ${data.message}`);
                            } catch (e) {
                                setTestResult('FFmpeg Test Failed');
                            }
                        }}>Test FFmpeg</button>
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
            )
            }

            {activeTab === 'users' && <AdminUsers />}
            {activeTab === 'rules' && <AdminRules />}
            {activeTab === 'billing' && <AdminBilling />}
            {activeTab === 'analytics' && <AdminAnalytics />}
            {activeTab === 'ai-rules' && <AdminAIRules />}
            {activeTab === 'beginner-rules' && <AdminBeginnerRules />}
            {activeTab === 'lesson-prompts' && <AdminLessonPrompts />}

            {/* Floating AI Button */}
            {
                !aiChatOpen && (
                    <button
                        onClick={() => setAiChatOpen(true)}
                        style={{
                            position: 'fixed',
                            bottom: '2rem',
                            right: '2rem',
                            width: '60px',
                            height: '60px',
                            borderRadius: '50%',
                            background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                            border: 'none',
                            boxShadow: '0 4px 12px rgba(0,0,0,0.3)',
                            cursor: 'pointer',
                            zIndex: 1000,
                            fontSize: '24px',
                            transition: 'transform 0.2s ease'
                        }}
                        onMouseEnter={(e) => e.currentTarget.style.transform = 'scale(1.1)'}
                        onMouseLeave={(e) => e.currentTarget.style.transform = 'scale(1)'}
                        title="AI Admin Assistant"
                    >
                        🤖
                    </button>
                )
            }

            {/* AI Chat Panel */}
            {aiChatOpen && <AIChatPanel onClose={() => setAiChatOpen(false)} />}
        </div >
    );
}
