import { useState, useEffect } from 'react';

interface BillingPackage {
    id: number;
    min_amount_rub: number;
    discount_percent: number;
    description: string;
    is_active: boolean;
    sort_order: number;
}

interface Referral {
    id: number;
    referrer_user_id: number;
    referred_user_id: number;
    referral_code: string;
    status: string;
    created_at: string;
}

export default function AdminBilling() {
    const [packages, setPackages] = useState<BillingPackage[]>([]);
    const [referrals, setReferrals] = useState<Referral[]>([]);
    const [loading, setLoading] = useState(false);

    // New Package State
    const [newPkg, setNewPkg] = useState<Partial<BillingPackage>>({
        min_amount_rub: 1000,
        discount_percent: 0,
        description: '',
        is_active: true,
        sort_order: 0
    });

    useEffect(() => {
        fetchPackages();
        fetchReferrals();
    }, []);

    const fetchPackages = async () => {
        setLoading(true);
        try {
            const res = await fetch('/api/billing/packages');
            if (res.ok) {
                const data = await res.json();
                setPackages(data);
            }
        } catch (e) {
            console.error(e);
        } finally {
            setLoading(false);
        }
    };

    const fetchReferrals = async () => {
        try {
            const res = await fetch('/api/admin/billing/referrals');
            if (res.ok) {
                const data = await res.json();
                setReferrals(data);
            }
        } catch (e) {
            console.error(e);
        }
    };

    const handleCreatePackage = async () => {
        try {
            const res = await fetch('/api/admin/billing/packages', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(newPkg)
            });
            if (res.ok) {
                alert('Package created');
                fetchPackages();
            } else {
                alert('Error creating package');
            }
        } catch (e) {
            alert(`Error: ${e}`);
        }
    };

    const handleBlockReferral = async (id: number) => {
        if (!confirm('Block this referral?')) return;
        try {
            const res = await fetch(`/api/admin/billing/referrals/${id}/block`, { method: 'POST' });
            if (res.ok) fetchReferrals();
        } catch (e) {
            console.error(e);
        }
    };

    return (
        <div>
            <h3>Billing Management</h3>

            <div style={{ marginBottom: '30px', padding: '20px', background: '#2a2a2a', borderRadius: '8px' }}>
                <h4>Deposit Packages</h4>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: '10px', marginBottom: '20px' }}>
                    {packages.map(pkg => (
                        <div key={pkg.id} style={{ padding: '10px', border: '1px solid #444', borderRadius: '4px' }}>
                            <div><strong>{pkg.min_amount_rub} RUB</strong></div>
                            <div>Discount: {pkg.discount_percent}%</div>
                            <div>{pkg.description}</div>
                            <div>Active: {pkg.is_active ? 'Yes' : 'No'}</div>
                        </div>
                    ))}
                </div>

                <h5>Add New Package</h5>
                <div style={{ display: 'flex', gap: '10px', alignItems: 'flex-end', flexWrap: 'wrap' }}>
                    <label>
                        Min Amount (RUB):
                        <input type="number" value={newPkg.min_amount_rub} onChange={e => setNewPkg({ ...newPkg, min_amount_rub: Number(e.target.value) })} style={{ display: 'block' }} />
                    </label>
                    <label>
                        Discount (%):
                        <input type="number" value={newPkg.discount_percent} onChange={e => setNewPkg({ ...newPkg, discount_percent: Number(e.target.value) })} style={{ display: 'block' }} />
                    </label>
                    <label>
                        Description:
                        <input type="text" value={newPkg.description} onChange={e => setNewPkg({ ...newPkg, description: e.target.value })} style={{ display: 'block' }} />
                    </label>
                    <button onClick={handleCreatePackage}>Create Package</button>
                </div>
            </div>

            <div style={{ padding: '20px', background: '#2a2a2a', borderRadius: '8px' }}>
                <h4>Referrals</h4>
                <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                    <thead>
                        <tr style={{ textAlign: 'left', borderBottom: '1px solid #444' }}>
                            <th>ID</th>
                            <th>Code</th>
                            <th>Referrer ID</th>
                            <th>Referred ID</th>
                            <th>Status</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        {referrals.map(ref => (
                            <tr key={ref.id} style={{ borderBottom: '1px solid #333' }}>
                                <td>{ref.id}</td>
                                <td>{ref.referral_code}</td>
                                <td>{ref.referrer_user_id}</td>
                                <td>{ref.referred_user_id}</td>
                                <td>{ref.status}</td>
                                <td>
                                    {ref.status !== 'blocked' && (
                                        <button onClick={() => handleBlockReferral(ref.id)} style={{ background: 'red', color: 'white' }}>Block</button>
                                    )}
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
}
