import { useState, useEffect } from 'react';
import AdminVoiceStack from './AdminVoiceStack';

interface AnalyticsBucket {
    period_start: string;
    total_minutes: number;
    total_revenue: number;
    sessions_count: number;
}

interface AnalyticsResponse {
    grouping: string;
    buckets: AnalyticsBucket[];
    totals: {
        total_minutes: number;
        total_revenue: number;
        sessions_count: number;
    };
}

interface PauseEvent {
    pause_id: number;
    lesson_session_id: number;
    paused_at: string;
    resumed_at: string | null;
    summary_text: string | null;
    student_id: number;
    student_email: string;
    pause_reason: string | null;
}

interface PauseResponse {
    days: number;
    limit: number;
    items: PauseEvent[];
}

export default function AdminAnalytics() {
    const [fromDate, setFromDate] = useState(() => {
        const d = new Date();
        d.setDate(d.getDate() - 7);
        return d.toISOString().split('T')[0];
    });
    const [toDate, setToDate] = useState(() => new Date().toISOString().split('T')[0]);
    const [groupBy, setGroupBy] = useState('day');
    const [data, setData] = useState<AnalyticsResponse | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');
    const [pauses, setPauses] = useState<PauseResponse | null>(null);

    useEffect(() => {
        fetchData();
    }, [fromDate, toDate, groupBy]);

    useEffect(() => {
        fetchPauses();
    }, [fromDate, toDate]);

    const fetchData = async () => {
        setLoading(true);
        setError('');
        try {
            // Append time to dates to cover full days
            const start = new Date(fromDate);
            const end = new Date(toDate);
            end.setHours(23, 59, 59, 999);

            const params = new URLSearchParams({
                from_date: start.toISOString(),
                to_date: end.toISOString(),
                group_by: groupBy
            });

            const res = await fetch(`/api/admin/analytics/revenue/minutes?${params}`);
            if (!res.ok) throw new Error(await res.text());
            const json = await res.json();
            setData(json);
        } catch (e: any) {
            setError(e.message);
        } finally {
            setLoading(false);
        }
    };

    const fetchPauses = async () => {
        try {
            const days = Math.max(1, Math.round((new Date(toDate).getTime() - new Date(fromDate).getTime()) / (1000 * 60 * 60 * 24)) || 7);
            const res = await fetch(`/api/admin/analytics/lesson-pauses/recent?days=${days}&limit=50`);
            if (!res.ok) throw new Error(await res.text());
            const json = await res.json();
            setPauses(json);
        } catch (e) {
            // Pause analytics are optional; log to console but don't block main analytics
            console.error('Failed to load pause analytics', e);
        }
    };

    if (loading && !data) return <div>Loading analytics...</div>;
    if (error) return <div style={{ color: 'red' }}>Error: {error}</div>;
    if (!data) return <div>No data</div>;

    // Chart Helpers
    const maxRevenue = Math.max(...data.buckets.map(b => b.total_revenue), 1);
    const chartHeight = 200;

    return (
        <div>
            <AdminVoiceStack />
            <h3>Revenue & Usage Analytics</h3>

            {/* Controls */}
            <div style={{ display: 'flex', gap: '1rem', marginBottom: '1rem', alignItems: 'center' }}>
                <label>
                    From: <input type="date" value={fromDate} onChange={e => setFromDate(e.target.value)} />
                </label>
                <label>
                    To: <input type="date" value={toDate} onChange={e => setToDate(e.target.value)} />
                </label>
                <label>
                    Group By:
                    <select value={groupBy} onChange={e => setGroupBy(e.target.value)} style={{ marginLeft: '0.5rem' }}>
                        <option value="day">Day</option>
                        <option value="hour">Hour</option>
                    </select>
                </label>
                <button onClick={fetchData}>Refresh</button>
            </div>

            {/* Summary Cards */}
            <div style={{ display: 'flex', gap: '1rem', marginBottom: '2rem' }}>
                <div style={cardStyle}>
                    <div style={labelStyle}>Total Revenue</div>
                    <div style={valueStyle}>{data.totals.total_revenue.toFixed(2)} RUB</div>
                </div>
                <div style={cardStyle}>
                    <div style={labelStyle}>Total Minutes</div>
                    <div style={valueStyle}>{data.totals.total_minutes} min</div>
                </div>
                <div style={cardStyle}>
                    <div style={labelStyle}>Sessions</div>
                    <div style={valueStyle}>{data.totals.sessions_count}</div>
                </div>
            </div>

            {/* Chart */}
            <div style={{ marginBottom: '2rem', background: '#222', padding: '1rem', borderRadius: '8px' }}>
                <h4>Revenue Trend</h4>
                <div style={{ display: 'flex', alignItems: 'flex-end', height: chartHeight, gap: '4px', overflowX: 'auto' }}>
                    {data.buckets.map((b, i) => {
                        const height = (b.total_revenue / maxRevenue) * chartHeight;
                        return (
                            <div key={i} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', minWidth: '40px' }}>
                                <div
                                    title={`${new Date(b.period_start).toLocaleDateString()} ${groupBy === 'hour' ? new Date(b.period_start).getHours() + ':00' : ''}: ${b.total_revenue} RUB`}
                                    style={{
                                        width: '30px',
                                        height: `${height}px`,
                                        background: '#4CAF50',
                                        borderRadius: '4px 4px 0 0',
                                        transition: 'height 0.3s'
                                    }}
                                />
                                <span style={{ fontSize: '10px', marginTop: '4px', color: '#aaa' }}>
                                    {groupBy === 'day'
                                        ? new Date(b.period_start).getDate()
                                        : new Date(b.period_start).getHours()}
                                </span>
                            </div>
                        );
                    })}
                </div>
            </div>

            {/* Table */}
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', marginBottom: '2rem' }}>
                <thead>
                    <tr style={{ borderBottom: '1px solid #444' }}>
                        <th style={{ padding: '8px' }}>Period</th>
                        <th style={{ padding: '8px' }}>Revenue (RUB)</th>
                        <th style={{ padding: '8px' }}>Minutes</th>
                        <th style={{ padding: '8px' }}>Sessions</th>
                    </tr>
                </thead>
                <tbody>
                    {data.buckets.map((b, i) => (
                        <tr key={i} style={{ borderBottom: '1px solid #333' }}>
                            <td style={{ padding: '8px' }}>
                                {new Date(b.period_start).toLocaleString()}
                            </td>
                            <td style={{ padding: '8px', color: '#4CAF50' }}>{b.total_revenue.toFixed(2)}</td>
                            <td style={{ padding: '8px' }}>{b.total_minutes}</td>
                            <td style={{ padding: '8px' }}>{b.sessions_count}</td>
                        </tr>
                    ))}
                </tbody>
            </table>

            {/* Recent Lesson Pauses */}
            {pauses && pauses.items.length > 0 && (
                <div style={{ marginTop: '2rem' }}>
                    <h4>Recent Lesson Pauses (last {pauses.days} day(s))</h4>
                    <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.9rem' }}>
                        <thead>
                            <tr style={{ borderBottom: '1px solid #444' }}>
                                <th style={{ padding: '6px' }}>When Paused</th>
                                <th style={{ padding: '6px' }}>Student</th>
                                <th style={{ padding: '6px' }}>Lesson ID</th>
                                <th style={{ padding: '6px' }}>Resumed?</th>
                                <th style={{ padding: '6px' }}>Summary (before break)</th>
                            </tr>
                        </thead>
                        <tbody>
                            {pauses.items.map((p) => (
                                <tr key={p.pause_id} style={{ borderBottom: '1px solid #333' }}>
                                    <td style={{ padding: '6px' }}>{new Date(p.paused_at).toLocaleString()}</td>
                                    <td style={{ padding: '6px' }}>{p.student_email}</td>
                                    <td style={{ padding: '6px' }}>{p.lesson_session_id}</td>
                                    <td style={{ padding: '6px' }}>{p.resumed_at ? 'Yes' : 'No'}</td>
                                    <td style={{ padding: '6px', maxWidth: '400px' }}>{p.summary_text || '-'}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}
        </div>
    );
}

const cardStyle = {
    background: '#333',
    padding: '1rem',
    borderRadius: '8px',
    flex: 1,
    textAlign: 'center' as const
};

const labelStyle = {
    fontSize: '0.9rem',
    color: '#aaa',
    marginBottom: '0.5rem'
};

const valueStyle = {
    fontSize: '1.5rem',
    fontWeight: 'bold',
    color: '#fff'
};
