import { useState, useEffect } from 'react';

interface VoiceStackInfo {
    stt: {
        provider: string;
        model: string;
        streaming: boolean;
    };
    tts: {
        provider: string;
        model: string;
        streaming: boolean;
    };
    latency: {
        tts_avg_ms: number;
        stt_avg_ms: number;
        samples: number;
    };
}

export default function AdminVoiceStack() {
    const [info, setInfo] = useState<VoiceStackInfo | null>(null);
    const [loading, setLoading] = useState(false);

    const fetchInfo = async () => {
        setLoading(true);
        try {
            const res = await fetch('/api/admin/voice/stack');
            if (res.ok) {
                setInfo(await res.json());
            }
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchInfo();
        const interval = setInterval(fetchInfo, 5000); // Poll every 5s
        return () => clearInterval(interval);
    }, []);

    if (loading && !info) return <div>Loading Voice Stack...</div>;
    if (!info) return <div>No Voice Stack Info</div>;

    return (
        <div style={{ background: '#222', padding: '1rem', borderRadius: '8px', marginBottom: '2rem' }}>
            <h3>Voice Stack Health</h3>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                <div style={{ background: '#333', padding: '1rem', borderRadius: '4px' }}>
                    <h4 style={{ margin: '0 0 10px 0', color: '#4CAF50' }}>STT (Speech-to-Text)</h4>
                    <p><strong>Provider:</strong> {info.stt.provider}</p>
                    <p><strong>Model:</strong> {info.stt.model}</p>
                    <p><strong>Streaming:</strong> {info.stt.streaming ? '✅ Yes' : '❌ No'}</p>
                    <p><strong>Avg Latency:</strong> {info.latency.stt_avg_ms > 0 ? `${info.latency.stt_avg_ms} ms` : 'N/A'}</p>
                </div>

                <div style={{ background: '#333', padding: '1rem', borderRadius: '4px' }}>
                    <h4 style={{ margin: '0 0 10px 0', color: '#2196F3' }}>TTS (Text-to-Speech)</h4>
                    <p><strong>Provider:</strong> {info.tts.provider}</p>
                    <p><strong>Model:</strong> {info.tts.model}</p>
                    <p><strong>Streaming:</strong> {info.tts.streaming ? '✅ Yes' : '❌ No'}</p>
                    <p><strong>Avg Latency:</strong> {info.latency.tts_avg_ms > 0 ? `${info.latency.tts_avg_ms} ms` : 'N/A'}</p>
                </div>
            </div>

            <div style={{ marginTop: '1rem', fontSize: '0.9em', color: '#888' }}>
                Stats based on last {info.latency.samples} samples.
            </div>
        </div>
    );
}
