import { useState, useEffect } from 'react';

interface ProviderStatus {
    has_key: boolean;
    masked_key: string;
    status: string; // ok, invalid, quota, error, unknown
    last_checked_at: string | null;
    last_error: string | null;
}

interface TokensStatus {
    openai: ProviderStatus;
    yandex_speechkit: ProviderStatus;
}

export default function TokensPanel() {
    const [tokensStatus, setTokensStatus] = useState<TokensStatus | null>(null);
    const [testing, setTesting] = useState<Record<string, boolean>>({});
    const [error, setError] = useState('');

    const loadStatus = async () => {
        try {
            const res = await fetch('/api/admin/tokens/status');
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();
            setTokensStatus(data);
        } catch (e) {
            setError('Failed to load token status');
            console.error('Token status error:', e);
        }
    };

    useEffect(() => {
        loadStatus();
    }, []);

    const testToken = async (provider: string) => {
        setTesting(prev => ({ ...prev, [provider]: true }));
        setError('');
        try {
            const res = await fetch('/api/admin/tokens/test', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ provider })
            });
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            await loadStatus(); // Reload status after test
        } catch (e) {
            setError(`Failed to test ${provider} token`);
            console.error(`Token test error for ${provider}:`, e);
        } finally {
            setTesting(prev => ({ ...prev, [provider]: false }));
        }
    };

    const getStatusColor = (status: string): string => {
        switch (status) {
            case 'ok': return '#4CAF50'; // green
            case 'invalid': return '#f44336'; // red
            case 'error': return '#f44336'; // red
            case 'quota': return '#FF9800'; // orange
            case 'unknown': return '#9E9E9E'; // gray
            default: return '#9E9E9E';
        }
    };

    const getStatusLabel = (status: string): string => {
        switch (status) {
            case 'ok': return '✓ OK';
            case 'invalid': return '✗ INVALID';
            case 'error': return '✗ ERROR';
            case 'quota': return '⚠ QUOTA';
            case 'unknown': return '? UNKNOWN';
            default: return status.toUpperCase();
        }
    };

    const formatLastChecked = (timestamp: string | null): string => {
        if (!timestamp) return '—';
        const date = new Date(timestamp);
        const now = new Date();
        const diff = now.getTime() - date.getTime();
        const minutes = Math.floor(diff / 60000);
        const hours = Math.floor(minutes / 60);
        const days = Math.floor(hours / 24);

        if (minutes < 1) return 'Just now';
        if (minutes < 60) return `${minutes}m ago`;
        if (hours < 24) return `${hours}h ago`;
        return `${days}d ago`;
    };

    if (!tokensStatus) {
        return <div>Loading token status...</div>;
    }

    const providers = [
        { id: 'openai', name: 'OpenAI', data: tokensStatus.openai },
        { id: 'yandex_speechkit', name: 'Yandex SpeechKit', data: tokensStatus.yandex_speechkit }
    ];

    return (
        <div style={{ marginTop: '30px', borderTop: '2px solid #ddd', paddingTop: '20px' }}>
            <h3>🔑 AI Tokens Health Panel</h3>
            <p style={{ fontSize: '14px', color: '#666', marginBottom: '20px' }}>
                Monitor and test your AI provider API keys
            </p>

            {error && (
                <div style={{ padding: '10px', background: '#ffebee', color: '#c62828', borderRadius: '4px', marginBottom: '15px' }}>
                    {error}
                </div>
            )}

            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '14px' }}>
                <thead>
                    <tr style={{ borderBottom: '2px solid #ddd' }}>
                        <th style={{ textAlign: 'left', padding: '10px' }}>Provider</th>
                        <th style={{ textAlign: 'left', padding: '10px' }}>Key</th>
                        <th style={{ textAlign: 'left', padding: '10px' }}>Status</th>
                        <th style={{ textAlign: 'left', padding: '10px' }}>Last Checked</th>
                        <th style={{ textAlign: 'left', padding: '10px' }}>Error</th>
                        <th style={{ textAlign: 'center', padding: '10px' }}>Action</th>
                    </tr>
                </thead>
                <tbody>
                    {providers.map(({ id, name, data }) => (
                        <tr key={id} style={{ borderBottom: '1px solid #eee' }}>
                            <td style={{ padding: '12px', fontWeight: '500' }}>{name}</td>
                            <td style={{ padding: '12px', fontFamily: 'monospace', fontSize: '12px' }}>
                                {data.has_key ? data.masked_key : <span style={{ color: '#999' }}>Not set</span>}
                            </td>
                            <td style={{ padding: '12px' }}>
                                <span style={{
                                    display: 'inline-block',
                                    padding: '4px 8px',
                                    borderRadius: '4px',
                                    fontSize: '12px',
                                    fontWeight: 'bold',
                                    color: 'white',
                                    backgroundColor: getStatusColor(data.status)
                                }}>
                                    {getStatusLabel(data.status)}
                                </span>
                            </td>
                            <td style={{ padding: '12px', color: '#666' }}>
                                {formatLastChecked(data.last_checked_at)}
                            </td>
                            <td style={{ padding: '12px', fontSize: '12px', color: '#d32f2f', maxWidth: '200px' }}>
                                {data.last_error || '—'}
                            </td>
                            <td style={{ padding: '12px', textAlign: 'center' }}>
                                <button
                                    onClick={() => testToken(id)}
                                    disabled={testing[id] || !data.has_key}
                                    style={{
                                        padding: '6px 12px',
                                        fontSize: '12px',
                                        backgroundColor: testing[id] ? '#ccc' : '#2196F3',
                                        color: 'white',
                                        border: 'none',
                                        borderRadius: '4px',
                                        cursor: testing[id] || !data.has_key ? 'not-allowed' : 'pointer'
                                    }}
                                >
                                    {testing[id] ? '⏳ Testing...' : '🔬 Check Token'}
                                </button>
                            </td>
                        </tr>
                    ))}
                </tbody>
            </table>

            <div style={{ marginTop: '15px', padding: '10px', background: '#f5f5f5', borderRadius: '4px', fontSize: '12px', color: '#666' }}>
                <strong>Status Legend:</strong>
                <span style={{ marginLeft: '10px', color: '#4CAF50' }}>● OK</span> = Token is valid and working |
                <span style={{ marginLeft: '5px', color: '#f44336' }}>● INVALID</span> = Wrong key / Unauthorized |
                <span style={{ marginLeft: '5px', color: '#FF9800' }}>● QUOTA</span> = Rate limit / Quota exceeded |
                <span style={{ marginLeft: '5px', color: '#f44336' }}>● ERROR</span> = Other error |
                <span style={{ marginLeft: '5px', color: '#9E9E9E' }}>● UNKNOWN</span> = Not tested yet
            </div>

            <div style={{ marginTop: '10px', fontSize: '12px', color: '#999', fontStyle: 'italic' }}>
                💡 Tip: After updating an API key above, press "Check Token" to verify it works.
            </div>
        </div>
    );
}
