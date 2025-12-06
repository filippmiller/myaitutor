import { useState, useEffect } from 'react';
import DebugModal from './DebugModal';

interface ProviderStatus {
    has_key: boolean;
    masked_key: string;
    status: string;
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
    const [debugModalOpen, setDebugModalOpen] = useState(false);
    const [debugData, setDebugData] = useState<any>(null);

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
            if (!res.ok) {
                const errorText = await res.text();
                throw new Error(`HTTP ${res.status}: ${errorText}`);
            }
            const result = await res.json();

            // Show debug modal with full details
            setDebugData(result);
            setDebugModalOpen(true);

            // Reload status
            await loadStatus();
        } catch (e: any) {
            setError(`Failed to test ${provider} token: ${e.message}`);
            console.error(`Token test error for ${provider}:`, e);
        } finally {
            setTesting(prev => ({ ...prev, [provider]: false }));
        }
    };

    const getStatusColor = (status: string): string => {
        switch (status) {
            case 'ok': return '#10b981'; // emerald-500  
            case 'invalid': return '#ef4444'; // red-500
            case 'error': return '#ef4444';
            case 'quota': return '#f59e0b'; // amber-500
            case 'unknown': return '#6b7280'; // gray-500
            default: return '#6b7280';
        }
    };

    const getStatusIcon = (status: string): string => {
        switch (status) {
            case 'ok': return '✓';
            case 'invalid': return '✗';
            case 'error': return '✗';
            case 'quota': return '⚠';
            case 'unknown': return '?';
            default: return '?';
        }
    };

    const formatLastChecked = (timestamp: string | null): string => {
        if (!timestamp) return 'Never';
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
        return (
            <div style={{ padding: '20px', textAlign: 'center' }}>
                <div>Loading token status...</div>
            </div>
        );
    }

    const providers = [
        { id: 'openai', name: 'OpenAI', data: tokensStatus.openai },
        { id: 'yandex_speechkit', name: 'Yandex SpeechKit', data: tokensStatus.yandex_speechkit }
    ];

    return (
        <>
            <div style={{ marginTop: '40px', paddingTop: '30px', borderTop: '2px solid #374151' }}>
                <div style={{ marginBottom: '24px' }}>
                    <h3 style={{ fontSize: '20px', fontWeight: '600', marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                        🔑 AI Provider Tokens
                    </h3>
                    <p style={{ fontSize: '14px', color: '#9ca3af', margin: 0 }}>
                        Monitor API key health and test connections
                    </p>
                </div>

                {error && (
                    <div style={{
                        padding: '12px 16px',
                        background: 'linear-gradient(135deg, #fecaca 0%, #fca5a5 100%)',
                        color: '#7f1d1d',
                        borderRadius: '8px',
                        marginBottom: '20px',
                        border: '1px solid #f87171',
                        fontSize: '14px'
                    }}>
                        <strong>⚠ Error:</strong> {error}
                    </div>
                )}

                <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                    {providers.map(({ id, name, data }) => {
                        const statusColor = getStatusColor(data.status);
                        const statusIcon = getStatusIcon(data.status);

                        return (
                            <div
                                key={id}
                                style={{
                                    background: 'linear-gradient(135deg, #374151 0%, #1f2937 100%)',
                                    border: '1px solid #4b5563',
                                    borderRadius: '12px',
                                    padding: '20px',
                                    transition: 'all 0.2s ease',
                                    boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.3)'
                                }}
                            >
                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '16px' }}>
                                    <div style={{ flex: 1 }}>
                                        <h4 style={{ fontSize: '16px', fontWeight: '600', marginBottom: '12px', color: '#f3f4f6' }}>
                                            {name}
                                        </h4>

                                        <div style={{ display: 'grid', gridTemplateColumns: '120px 1fr', gap: '8px', fontSize: '13px' }}>
                                            <div style={{ color: '#9ca3af' }}>API Key:</div>
                                            <div
                                                style={{
                                                    fontFamily: 'monospace',
                                                    color: data.has_key ? '#d1d5db' : '#6b7280',
                                                    maxWidth: '260px',
                                                    overflow: 'hidden',
                                                    textOverflow: 'ellipsis',
                                                    whiteSpace: 'nowrap',
                                                }}
                                            >
                                                {data.has_key ? data.masked_key : 'Not configured'}
                                            </div>

                                            <div style={{ color: '#9ca3af' }}>Status:</div>
                                            <div>
                                                <span style={{
                                                    display: 'inline-flex',
                                                    alignItems: 'center',
                                                    gap: '6px',
                                                    padding: '4px 12px',
                                                    borderRadius: '6px',
                                                    fontSize: '12px',
                                                    fontWeight: 'bold',
                                                    color: 'white',
                                                    backgroundColor: statusColor
                                                }}>
                                                    <span>{statusIcon}</span>
                                                    <span>{data.status.toUpperCase()}</span>
                                                </span>
                                            </div>

                                            <div style={{ color: '#9ca3af' }}>Last Tested:</div>
                                            <div style={{ color: '#d1d5db' }}>
                                                {formatLastChecked(data.last_checked_at)}
                                            </div>

                                            {data.last_error && (
                                                <>
                                                    <div style={{ color: '#9ca3af' }}>Last Error:</div>
                                                    <div style={{ color: '#fca5a5', fontSize: '12px' }}>
                                                        {data.last_error}
                                                    </div>
                                                </>
                                            )}
                                        </div>
                                    </div>

                                    <button
                                        onClick={() => testToken(id)}
                                        disabled={testing[id] || !data.has_key}
                                        style={{
                                            padding: '10px 20px',
                                            fontSize: '14px',
                                            fontWeight: '600',
                                            background: testing[id] ? '#374151' : 'linear-gradient(135deg, #3b82f6 0%, #2563eb 100%)',
                                            color: 'white',
                                            border: 'none',
                                            borderRadius: '8px',
                                            cursor: testing[id] || !data.has_key ? 'not-allowed' : 'pointer',
                                            transition: 'all 0.2s ease',
                                            opacity: testing[id] || !data.has_key ? 0.5 : 1,
                                            boxShadow: testing[id] || !data.has_key ? 'none' : '0 2px 4px rgba(59, 130, 246, 0.4)',
                                            minWidth: '140px'
                                        }}
                                        onMouseOver={(e) => {
                                            if (!testing[id] && data.has_key) {
                                                e.currentTarget.style.transform = 'translateY(-1px)';
                                                e.currentTarget.style.boxShadow = '0 4px 8px rgba(59, 130, 246, 0.6)';
                                            }
                                        }}
                                        onMouseOut={(e) => {
                                            e.currentTarget.style.transform = 'translateY(0)';
                                            e.currentTarget.style.boxShadow = testing[id] || !data.has_key ? 'none' : '0 2px 4px rgba(59, 130, 246, 0.4)';
                                        }}
                                    >
                                        {testing[id] ? '⏳ Testing...' : '🔬 Test Connection'}
                                    </button>
                                </div>
                            </div>
                        );
                    })}
                </div>

                <div style={{
                    marginTop: '20px',
                    padding: '12px 16px',
                    background: '#1f2937',
                    borderRadius: '8px',
                    fontSize: '12px',
                    color: '#9ca3af',
                    border: '1px solid #374151'
                }}>
                    <strong style={{ color: '#d1d5db' }}>💡 Tip:</strong> After updating an API key above, use <strong>Test Connection</strong> to verify it works. The test will show you the full HTTP request/response for debugging.
                </div>
            </div>

            {debugModalOpen && debugData && (
                <DebugModal
                    data={debugData}
                    onClose={() => setDebugModalOpen(false)}
                />
            )}
        </>
    );
}
