import { useState, useEffect } from 'react';

export default function Admin() {
    const [apiKey, setApiKey] = useState('');
    const [model, setModel] = useState('gpt-4o-mini');
    const [msg, setMsg] = useState('');

    useEffect(() => {
        fetch('/api/admin/settings')
            .then(res => res.json())
            .then(data => {
                if (data.openai_api_key) setApiKey(data.openai_api_key);
                if (data.default_model) setModel(data.default_model);
            });
    }, []);

    const save = async () => {
        const res = await fetch('/api/admin/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ openai_api_key: apiKey, default_model: model })
        });
        if (res.ok) setMsg('Saved!');
        else setMsg('Error saving');
    };

    return (
        <div className="card">
            <h2>Admin Settings</h2>
            <label>
                OpenAI API Key:
                <input
                    type="password"
                    value={apiKey}
                    onChange={e => setApiKey(e.target.value)}
                    placeholder="sk-..."
                />
            </label>
            <label>
                Model:
                <select value={model} onChange={e => setModel(e.target.value)}>
                    <option value="gpt-4o-mini">gpt-4o-mini</option>
                    <option value="gpt-4-turbo">gpt-4-turbo</option>
                    <option value="gpt-3.5-turbo">gpt-3.5-turbo</option>
                </select>
            </label>
            <button onClick={save}>Save</button>
            {msg && <p>{msg}</p>}
        </div>
    );
}
