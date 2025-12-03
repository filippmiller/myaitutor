import { useState, useEffect } from 'react';

export default function AdminBeginnerRules() {
    const [jsonContent, setJsonContent] = useState('');
    const [loading, setLoading] = useState(true);
    const [msg, setMsg] = useState('');

    useEffect(() => {
        fetch('/api/admin/beginner-rules')
            .then(res => res.json())
            .then(data => {
                setJsonContent(JSON.stringify(data, null, 2));
                setLoading(false);
            })
            .catch(err => {
                console.error(err);
                setLoading(false);
            });
    }, []);

    const save = async () => {
        try {
            const parsed = JSON.parse(jsonContent);
            const res = await fetch('/api/admin/beginner-rules', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(parsed)
            });
            if (res.ok) setMsg('Saved successfully!');
            else setMsg('Error saving');
        } catch (e) {
            setMsg('Invalid JSON format');
        }
    };

    return (
        <div>
            <h3>Absolute Beginner Curriculum (JSON)</h3>
            <p style={{ color: '#888', marginBottom: '1rem' }}>
                Edit the raw JSON rules for the Absolute Beginner curriculum. These rules are injected into the system prompt for students with level "A1" or "Beginner".
            </p>

            {loading ? <p>Loading...</p> : (
                <textarea
                    value={jsonContent}
                    onChange={e => setJsonContent(e.target.value)}
                    style={{
                        width: '100%',
                        height: '600px',
                        fontFamily: 'monospace',
                        background: '#1a1a1a',
                        color: '#eee',
                        border: '1px solid #444',
                        padding: '1rem',
                        borderRadius: '4px',
                        fontSize: '14px',
                        lineHeight: '1.5'
                    }}
                    spellCheck={false}
                />
            )}

            <div style={{ marginTop: '1rem' }}>
                <button
                    onClick={save}
                    style={{
                        padding: '10px 20px',
                        background: '#4CAF50',
                        color: 'white',
                        border: 'none',
                        borderRadius: '4px',
                        cursor: 'pointer',
                        fontWeight: 'bold'
                    }}
                >
                    Save JSON Rules
                </button>
                {msg && <span style={{ marginLeft: '1rem', color: msg.includes('Error') || msg.includes('Invalid') ? '#ff6b6b' : '#48bb78' }}>{msg}</span>}
            </div>
        </div>
    );
}
