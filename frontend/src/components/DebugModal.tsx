import { useState } from 'react';

interface DebugModalProps {
    data: any;
    onClose: () => void;
}

export default function DebugModal({ data, onClose }: DebugModalProps) {
    const [activeTab, setActiveTab] = useState<'overview' | 'request' | 'response'>('overview');

    const formatJSON = (obj: any): string => {
        try {
            return JSON.stringify(obj, null, 2);
        } catch {
            return String(obj);
        }
    };

    const getStatusColor = (status: string): string => {
        switch (status) {
            case 'ok': return '#10b981';
            case 'invalid': return '#ef4444';
            case 'error': return '#ef4444';
            case 'quota': return '#f59e0b';
            case 'unknown': return '#6b7280';
            default: return '#6b7280';
        }
    };

    const httpStatus = data.debug_info?.http_status || 'N/A';
    const httpStatusColor = httpStatus === 200 ? '#10b981' : httpStatus >= 400 ? '#ef4444' : '#f59e0b';

    return (
        <div
            style={{
                position: 'fixed',
                top: 0,
                left: 0,
                right: 0,
                bottom: 0,
                background: 'rgba(0, 0, 0, 0.85)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                zIndex: 1000,
                padding: '20px'
            }}
            onClick={onClose}
        >
            <div
                style={{
                    background: 'linear-gradient(135deg, #1f2937 0%, #111827 100%)',
                    borderRadius: '16px',
                    maxWidth: '900px',
                    width: '100%',
                    maxHeight: '90vh',
                    overflow: 'hidden',
                    boxShadow: '0 20px 50px rgba(0, 0, 0, 0.8)',
                    border: '1px solid #374151',
                    display: 'flex',
                    flexDirection: 'column'
                }}
                onClick={(e) => e.stopPropagation()}
            >
                {/* Header */}
                <div style={{
                    padding: '20px 24px',
                    borderBottom: '1px solid #374151',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center'
                }}>
                    <div>
                        <h3 style={{ margin: 0, fontSize: '18px', fontWeight: '600', color: '#f3f4f6', marginBottom: '4px' }}>
                            🔬 API Connection Test Results
                        </h3>
                        <p style={{ margin: 0, fontSize: '13px', color: '#9ca3af' }}>
                            {data.provider} • {new Date(data.last_checked_at).toLocaleString()}
                        </p>
                    </div>
                    <button
                        onClick={onClose}
                        style={{
                            background: '#374151',
                            border: 'none',
                            color: '#f3f4f6',
                            fontSize: '24px',
                            cursor: 'pointer',
                            borderRadius: '8px',
                            width: '36px',
                            height: '36px',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            transition: 'all 0.2s ease'
                        }}
                        onMouseOver={(e) => {
                            e.currentTarget.style.background = '#4b5563';
                        }}
                        onMouseOut={(e) => {
                            e.currentTarget.style.background = '#374151';
                        }}
                    >
                        ×
                    </button>
                </div>

                {/* Tabs */}
                <div style={{
                    display: 'flex',
                    gap: '8px',
                    padding: '0 24px',
                    borderBottom: '1px solid #374151',
                    background: '#111827'
                }}>
                    {(['overview', 'request', 'response'] as const).map(tab => (
                        <button
                            key={tab}
                            onClick={() => setActiveTab(tab)}
                            style={{
                                padding: '12px 20px',
                                background: activeTab === tab ? '#1f2937' : 'transparent',
                                border: 'none',
                                borderBottom: activeTab === tab ? '2px solid #3b82f6' : '2px solid transparent',
                                color: activeTab === tab ? '#f3f4f6' : '#9ca3af',
                                fontSize: '14px',
                                fontWeight: activeTab === tab ? '600' : '400',
                                cursor: 'pointer',
                                transition: 'all 0.2s ease'
                            }}
                        >
                            {tab.charAt(0).toUpperCase() + tab.slice(1)}
                        </button>
                    ))}
                </div>

                {/* Content */}
                <div style={{
                    flex: 1,
                    overflow: 'auto',
                    padding: '24px'
                }}>
                    {activeTab === 'overview' && (
                        <div>
                            <div style={{
                                background: '#111827',
                                border: `2px solid ${getStatusColor(data.status)}`,
                                borderRadius: '12px',
                                padding: '20px',
                                marginBottom: '20px'
                            }}>
                                <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '12px' }}>
                                    <span style={{
                                        fontSize: '32px',
                                        padding: '8px 16px',
                                        background: getStatusColor(data.status),
                                        borderRadius: '8px'
                                    }}>
                                        {data.status === 'ok' ? '✓' : data.status === 'invalid' || data.status === 'error' ? '✗' : '⚠'}
                                    </span>
                                    <div>
                                        <div style={{ fontSize: '20px', fontWeight: '600', color: '#f3f4f6' }}>
                                            {data.status.toUpperCase()}
                                        </div>
                                        <div style={{ fontSize: '14px', color: '#9ca3af' }}>
                                            {data.message}
                                        </div>
                                    </div>
                                </div>
                            </div>

                            <div style={{
                                display: 'grid',
                                gridTemplateColumns: '1fr 1fr',
                                gap: '16px',
                                marginBottom: '20px'
                            }}>
                                <div style={{
                                    background: '#111827',
                                    padding: '16px',
                                    borderRadius: '8px',
                                    border: '1px solid #374151'
                                }}>
                                    <div style={{ fontSize: '12px', color: '#9ca3af', marginBottom: '4px' }}>
                                        HTTP STATUS CODE
                                    </div>
                                    <div style={{
                                        fontSize: '24px',
                                        fontWeight: '700',
                                        color: httpStatusColor,
                                        fontFamily: 'monospace'
                                    }}>
                                        {httpStatus}
                                    </div>
                                </div>

                                <div style={{
                                    background: '#111827',
                                    padding: '16px',
                                    borderRadius: '8px',
                                    border: '1px solid #374151'
                                }}>
                                    <div style={{ fontSize: '12px', color: '#9ca3af', marginBottom: '4px' }}>
                                        PROVIDER
                                    </div>
                                    <div style={{ fontSize: '18px', fontWeight: '600', color: '#f3f4f6' }}>
                                        {data.debug_info?.provider || data.provider}
                                    </div>
                                </div>
                            </div>

                            {data.debug_info?.error && (
                                <div style={{
                                    background: '#7f1d1d',
                                    border: '1px solid #991b1b',
                                    borderRadius: '8px',
                                    padding: '16px',
                                    marginTop: '16px'
                                }}>
                                    <div style={{ fontSize: '12px', fontWeight: '600', color: '#fca5a5', marginBottom: '8px' }}>
                                        ERROR DETAILS
                                    </div>
                                    <div style={{ fontSize: '13px', color: '#fecaca', fontFamily: 'monospace', whiteSpace: 'pre-wrap' }}>
                                        {formatJSON(data.debug_info.error)}
                                    </div>
                                </div>
                            )}
                        </div>
                    )}

                    {activeTab === 'request' && (
                        <div>
                            <pre style={{
                                background: '#0a0e14',
                                color: '#d1d5db',
                                padding: '20px',
                                borderRadius: '8px',
                                fontSize: '13px',
                                fontFamily: 'Monaco, Menlo, "Courier New", monospace',
                                overflow: 'auto',
                                margin: 0,
                                border: '1px solid #374151',
                                lineHeight: '1.6'
                            }}>
                                <div style={{ color: '#10b981', marginBottom: '8px' }}>
                                    # HTTP REQUEST
                                </div>
                                <div>
                                    <span style={{ color: '#3b82f6' }}>{data.debug_info?.request?.method || 'POST'}</span>
                                    {' '}
                                    <span style={{ color: '#f59e0b' }}>{data.debug_info?.request?.url || 'N/A'}</span>
                                </div>
                                <br />
                                <div style={{ color: '#10b981' }}># HEADERS</div>
                                {formatJSON(data.debug_info?.request?.headers || {})}
                                <br />
                                <div style={{ color: '#10b981' }}># BODY</div>
                                {formatJSON(data.debug_info?.request?.body || {})}
                            </pre>
                        </div>
                    )}

                    {activeTab === 'response' && (
                        <div>
                            <pre style={{
                                background: '#0a0e14',
                                color: '#d1d5db',
                                padding: '20px',
                                borderRadius: '8px',
                                fontSize: '13px',
                                fontFamily: 'Monaco, Menlo, "Courier New", monospace',
                                overflow: 'auto',
                                margin: 0,
                                border: '1px solid #374151',
                                lineHeight: '1.6'
                            }}>
                                <div style={{ color: '#10b981', marginBottom: '8px' }}>
                                    # HTTP RESPONSE
                                </div>
                                <div>
                                    <span style={{ color: '#3b82f6' }}>HTTP/1.1</span>
                                    {' '}
                                    <span style={{ color: httpStatusColor, fontWeight: 'bold' }}>
                                        {httpStatus}
                                    </span>
                                </div>
                                <br />
                                {data.debug_info?.response ? (
                                    <>
                                        <div style={{ color: '#10b981' }}># RESPONSE BODY</div>
                                        {formatJSON(data.debug_info.response)}
                                    </>
                                ) : data.debug_info?.error ? (
                                    <>
                                        <div style={{ color: '#ef4444' }}># ERROR RESPONSE</div>
                                        {formatJSON(data.debug_info.error)}
                                    </>
                                ) : (
                                    <div style={{ color: '#6b7280' }}>(No response data available)</div>
                                )}
                            </pre>
                        </div>
                    )}
                </div>

                {/* Footer */}
                <div style={{
                    padding: '16px 24px',
                    borderTop: '1px solid #374151',
                    display: 'flex',
                    justifyContent: 'flex-end',
                    background: '#111827'
                }}>
                    <button
                        onClick={onClose}
                        style={{
                            padding: '10px 24px',
                            fontSize: '14px',
                            fontWeight: '600',
                            background: '#3b82f6',
                            color: 'white',
                            border: 'none',
                            borderRadius: '8px',
                            cursor: 'pointer',
                            transition: 'all 0.2s ease'
                        }}
                        onMouseOver={(e) => {
                            e.currentTarget.style.background = '#2563eb';
                        }}
                        onMouseOut={(e) => {
                            e.currentTarget.style.background = '#3b82f6';
                        }}
                    >
                        Close
                    </button>
                </div>
            </div>
        </div>
    );
}
