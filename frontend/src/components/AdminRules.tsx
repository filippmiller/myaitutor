import { useState, useEffect } from 'react';

interface SystemRule {
    id: number;
    rule_key: string;
    rule_text: string;
    enabled: boolean;
    sort_order: number;
}

export default function AdminRules() {
    const [rules, setRules] = useState<SystemRule[]>([]);
    const [loading, setLoading] = useState(false);
    const [editingId, setEditingId] = useState<number | null>(null);
    const [editForm, setEditForm] = useState<Partial<SystemRule>>({});

    useEffect(() => {
        fetchRules();
    }, []);

    const fetchRules = async () => {
        setLoading(true);
        try {
            const res = await fetch('/api/admin/system-rules');
            if (res.ok) {
                const data = await res.json();
                setRules(data);
            }
        } catch (e) {
            console.error(e);
        } finally {
            setLoading(false);
        }
    };

    const handleEdit = (rule: SystemRule) => {
        setEditingId(rule.id);
        setEditForm(rule);
    };

    const handleSave = async () => {
        if (!editingId) return;
        try {
            const res = await fetch(`/api/admin/system-rules/${editingId}`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(editForm)
            });
            if (res.ok) {
                setEditingId(null);
                fetchRules();
            }
        } catch (e) {
            console.error(e);
        }
    };

    return (
        <div>
            <h3>System Rules</h3>
            {loading && <p>Loading...</p>}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                {rules.map(rule => (
                    <div key={rule.id} style={{ padding: '1rem', border: '1px solid #444', borderRadius: '4px', background: rule.enabled ? '#2a2a2a' : '#1a1a1a' }}>
                        {editingId === rule.id ? (
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                                <label>
                                    Text:
                                    <textarea
                                        value={editForm.rule_text || ''}
                                        onChange={e => setEditForm({ ...editForm, rule_text: e.target.value })}
                                        style={{ width: '100%', minHeight: '60px' }}
                                    />
                                </label>
                                <label>
                                    Order:
                                    <input
                                        type="number"
                                        value={editForm.sort_order || 0}
                                        onChange={e => setEditForm({ ...editForm, sort_order: parseInt(e.target.value) })}
                                    />
                                </label>
                                <label>
                                    <input
                                        type="checkbox"
                                        checked={editForm.enabled || false}
                                        onChange={e => setEditForm({ ...editForm, enabled: e.target.checked })}
                                    /> Enabled
                                </label>
                                <div>
                                    <button onClick={handleSave}>Save</button>
                                    <button onClick={() => setEditingId(null)} style={{ marginLeft: '0.5rem' }}>Cancel</button>
                                </div>
                            </div>
                        ) : (
                            <div>
                                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                                    <strong>{rule.rule_key} (Order: {rule.sort_order})</strong>
                                    <button onClick={() => handleEdit(rule)}>Edit</button>
                                </div>
                                <p style={{ color: rule.enabled ? '#eee' : '#777' }}>{rule.rule_text}</p>
                                {!rule.enabled && <small>(Disabled)</small>}
                            </div>
                        )}
                    </div>
                ))}
            </div>
        </div>
    );
}
