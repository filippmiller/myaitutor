import { useState, useEffect } from 'react';

interface TutorRule {
    id: number;
    scope: string;
    type: string;
    title: string;
    description: string;
    trigger_condition?: string;
    action?: string;
    priority: number;
    is_active: boolean;
    source: string;
    created_at: string;
    updated_at: string;
}

interface RuleVersion {
    id: number;
    rule_id: number;
    title: string;
    description: string;
    changed_by: string;
    change_reason?: string;
    created_at: string;
}

export default function AdminAIRules() {
    const [rules, setRules] = useState<TutorRule[]>([]);
    const [loading, setLoading] = useState(true);
    const [selectedRule, setSelectedRule] = useState<TutorRule | null>(null);
    const [history, setHistory] = useState<RuleVersion[]>([]);
    const [scopeFilter, setScopeFilter] = useState<string>('all');
    const [activeFilter, setActiveFilter] = useState<boolean | null>(null);

    useEffect(() => {
        fetchRules();
    }, [scopeFilter, activeFilter]);

    const fetchRules = async () => {
        setLoading(true);
        try {
            let url = '/api/admin/ai/rules?';
            if (scopeFilter !== 'all') url += `scope=${scopeFilter}&`;
            if (activeFilter !== null) url += `is_active=${activeFilter}`;

            const res = await fetch(url);
            if (res.ok) {
                const data = await res.json();
                setRules(data);
            }
        } catch (e) {
            console.error('Failed to fetch rules:', e);
        } finally {
            setLoading(false);
        }
    };

    const fetchHistory = async (ruleId: number) => {
        try {
            const res = await fetch(`/api/admin/ai/rules/${ruleId}/history`);
            if (res.ok) {
                const data = await res.json();
                setHistory(data);
            }
        } catch (e) {
            console.error('Failed to fetch history:', e);
        }
    };

    const handleRuleClick = (rule: TutorRule) => {
        setSelectedRule(rule);
        fetchHistory(rule.id);
    };

    return (
        <div>
            <h3>AI-Managed Rules</h3>
            <p style={{ color: '#888', marginBottom: '1.5rem' }}>
                Rules created and managed by the AI Admin Assistant. Use the chat button to create or modify rules.
            </p>

            {/* Filters */}
            <div style={{ display: 'flex', gap: '1rem', marginBottom: '1.5rem', alignItems: 'center' }}>
                <label>
                    <span style={{ marginRight: '0.5rem' }}>Scope:</span>
                    <select
                        value={scopeFilter}
                        onChange={e => setScopeFilter(e.target.value)}
                        style={{ padding: '0.5rem', borderRadius: '4px' }}
                    >
                        <option value="all">All</option>
                        <option value="global">Global</option>
                        <option value="student">Student</option>
                        <option value="app">App</option>
                        <option value="session">Session</option>
                    </select>
                </label>

                <label>
                    <span style={{ marginRight: '0.5rem' }}>Status:</span>
                    <select
                        value={activeFilter === null ? 'all' : activeFilter ? 'active' : 'inactive'}
                        onChange={e => {
                            if (e.target.value === 'all') setActiveFilter(null);
                            else setActiveFilter(e.target.value === 'active');
                        }}
                        style={{ padding: '0.5rem', borderRadius: '4px' }}
                    >
                        <option value="all">All</option>
                        <option value="active">Active</option>
                        <option value="inactive">Inactive</option>
                    </select>
                </label>

                <button onClick={fetchRules} style={{ padding: '0.5rem 1rem' }}>
                    Refresh
                </button>
            </div>

            {loading ? (
                <p>Loading rules...</p>
            ) : (
                <div style={{ display: 'grid', gridTemplateColumns: selectedRule ? '1fr 1fr' : '1fr', gap: '1.5rem' }}>
                    {/* Rules List */}
                    <div>
                        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                            <thead>
                                <tr style={{ borderBottom: '2px solid #444' }}>
                                    <th style={{ padding: '0.75rem', textAlign: 'left' }}>Title</th>
                                    <th style={{ padding: '0.75rem', textAlign: 'left' }}>Scope</th>
                                    <th style={{ padding: '0.75rem', textAlign: 'left' }}>Type</th>
                                    <th style={{ padding: '0.75rem', textAlign: 'center' }}>Priority</th>
                                    <th style={{ padding: '0.75rem', textAlign: 'center' }}>Status</th>
                                    <th style={{ padding: '0.75rem', textAlign: 'left' }}>Source</th>
                                </tr>
                            </thead>
                            <tbody>
                                {rules.length === 0 ? (
                                    <tr>
                                        <td colSpan={6} style={{ padding: '2rem', textAlign: 'center', color: '#888' }}>
                                            No rules found. Use the AI chat to create some!
                                        </td>
                                    </tr>
                                ) : (
                                    rules.map(rule => (
                                        <tr
                                            key={rule.id}
                                            onClick={() => handleRuleClick(rule)}
                                            style={{
                                                borderBottom: '1px solid #333',
                                                cursor: 'pointer',
                                                background: selectedRule?.id === rule.id ? '#2a2a2a' : 'transparent'
                                            }}
                                        >
                                            <td style={{ padding: '0.75rem' }}>{rule.title}</td>
                                            <td style={{ padding: '0.75rem' }}>
                                                <span style={{
                                                    padding: '0.25rem 0.5rem',
                                                    borderRadius: '4px',
                                                    background: rule.scope === 'global' ? '#4a5568' : '#2d3748',
                                                    fontSize: '0.85em'
                                                }}>
                                                    {rule.scope}
                                                </span>
                                            </td>
                                            <td style={{ padding: '0.75rem', fontSize: '0.9em', color: '#aaa' }}>{rule.type}</td>
                                            <td style={{ padding: '0.75rem', textAlign: 'center' }}>{rule.priority}</td>
                                            <td style={{ padding: '0.75rem', textAlign: 'center' }}>
                                                <span style={{
                                                    padding: '0.25rem 0.5rem',
                                                    borderRadius: '4px',
                                                    background: rule.is_active ? '#2f855a' : '#742a2a',
                                                    fontSize: '0.85em'
                                                }}>
                                                    {rule.is_active ? 'Active' : 'Inactive'}
                                                </span>
                                            </td>
                                            <td style={{ padding: '0.75rem', fontSize: '0.85em', color: '#888' }}>
                                                {rule.source === 'ai_admin' ? '🤖 AI' : '👤 Manual'}
                                            </td>
                                        </tr>
                                    ))
                                )}
                            </tbody>
                        </table>
                    </div>

                    {/* Rule Details */}
                    {selectedRule && (
                        <div style={{
                            padding: '1.5rem',
                            background: '#1a1a1a',
                            borderRadius: '8px',
                            border: '1px solid #444'
                        }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '1rem' }}>
                                <h4 style={{ margin: 0 }}>{selectedRule.title}</h4>
                                <button onClick={() => setSelectedRule(null)} style={{ background: 'none', border: 'none', color: '#888', cursor: 'pointer', fontSize: '1.2em' }}>×</button>
                            </div>

                            <div style={{ marginBottom: '1rem' }}>
                                <strong>Description:</strong>
                                <p style={{ color: '#ccc', marginTop: '0.5rem' }}>{selectedRule.description}</p>
                            </div>

                            {selectedRule.trigger_condition && (
                                <div style={{ marginBottom: '1rem' }}>
                                    <strong>Trigger Condition:</strong>
                                    <pre style={{
                                        background: '#0d0d0d',
                                        padding: '0.75rem',
                                        borderRadius: '4px',
                                        fontSize: '0.85em',
                                        overflow: 'auto',
                                        marginTop: '0.5rem'
                                    }}>
                                        {selectedRule.trigger_condition}
                                    </pre>
                                </div>
                            )}

                            {selectedRule.action && (
                                <div style={{ marginBottom: '1rem' }}>
                                    <strong>Action:</strong>
                                    <pre style={{
                                        background: '#0d0d0d',
                                        padding: '0.75rem',
                                        borderRadius: '4px',
                                        fontSize: '0.85em',
                                        overflow: 'auto',
                                        marginTop: '0.5rem'
                                    }}>
                                        {selectedRule.action}
                                    </pre>
                                </div>
                            )}

                            <hr style={{ border: 'none', borderTop: '1px solid #444', margin: '1.5rem 0' }} />

                            <h5 style={{ marginTop: 0 }}>Version History</h5>
                            {history.length === 0 ? (
                                <p style={{ color: '#888', fontSize: '0.9em' }}>No history available</p>
                            ) : (
                                <div style={{ maxHeight: '300px', overflowY: 'auto' }}>
                                    {history.map((version, idx) => (
                                        <div key={version.id} style={{
                                            padding: '0.75rem',
                                            marginBottom: '0.5rem',
                                            background: idx === 0 ? '#2a2a2a' : '#1a1a1a',
                                            borderRadius: '4px',
                                            border: '1px solid #333'
                                        }}>
                                            <div style={{ fontSize: '0.85em', color: '#aaa', marginBottom: '0.25rem' }}>
                                                {new Date(version.created_at).toLocaleString()} by {version.changed_by}
                                            </div>
                                            <div style={{ fontSize: '0.9em' }}>{version.change_reason || 'No reason provided'}</div>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
