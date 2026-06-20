import React, { useState, useEffect, useCallback } from 'react';
import { Webhook, Plus, Trash2, CheckCircle, AlertCircle, RefreshCw, Activity } from 'lucide-react';
import { api } from '../../services/api';

export const WebhookSettings: React.FC = () => {
  const [webhooks, setWebhooks] = useState<any[]>([]);
  const [deliveries, setDeliveries] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  
  const [showCreate, setShowCreate] = useState(false);
  const [newWebhookSecret, setNewWebhookSecret] = useState<string | null>(null);

  const [formData, setFormData] = useState({
    name: '',
    url: '',
    event_types: 'user_registered,user_login'
  });

  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      const [whResp, delResp] = await Promise.all([
        api.get('/api/v1/organizations/webhooks'),
        api.get('/api/v1/organizations/webhooks/deliveries?limit=20')
      ]);
      setWebhooks(whResp.data || []);
      setDeliveries(delResp.data || []);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch Webhooks');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.name.trim() || !formData.url.trim()) return;
    try {
      const resp = await api.post('/api/v1/organizations/webhooks', {
        name: formData.name,
        url: formData.url,
        event_types: formData.event_types.split(',').map(s => s.trim())
      });
      setNewWebhookSecret(resp.data.secret);
      setFormData({ name: '', url: '', event_types: 'user_registered,user_login' });
      setShowCreate(false);
      fetchData();
    } catch (err: any) {
      setError(err.message || 'Failed to create webhook');
    }
  };

  const handleDelete = async (id: string) => {
    if (!window.confirm('Are you sure you want to delete this Webhook endpoint?')) return;
    try {
      await api.delete(`/api/v1/organizations/webhooks/${id}`);
      fetchData();
    } catch (err: any) {
      setError(err.message || 'Failed to delete webhook');
    }
  };

  if (loading) return <div>Loading webhooks...</div>;

  return (
    <div className="flex flex-col gap-lg">
      <div className="flex justify-between align-center">
        <div>
          <h2 className="text-xl font-bold">Webhooks</h2>
          <p style={{ color: 'var(--text-secondary)' }}>Send HTTP POST requests when events happen.</p>
        </div>
        <div className="flex gap-sm">
          <button className="btn btn-secondary" onClick={fetchData} title="Refresh">
            <RefreshCw size={18} />
          </button>
          <button className="btn btn-primary" onClick={() => setShowCreate(!showCreate)}>
            <Plus size={18} />
            Add Webhook
          </button>
        </div>
      </div>

      {error && (
        <div className="alert alert-error">
          <AlertCircle size={20} />
          <span>{error}</span>
        </div>
      )}

      {newWebhookSecret && (
        <div className="alert alert-success" style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
          <div className="flex align-center gap-sm">
            <CheckCircle size={20} />
            <strong>Webhook Created!</strong>
          </div>
          <p>Please copy your signing secret. It is used to verify the webhook signatures.</p>
          <code style={{ background: 'rgba(0,0,0,0.2)', padding: '0.5rem', borderRadius: '4px' }}>
            {newWebhookSecret}
          </code>
          <button className="btn btn-secondary btn-sm" onClick={() => setNewWebhookSecret(null)} style={{ alignSelf: 'flex-start' }}>
            Dismiss
          </button>
        </div>
      )}

      {showCreate && (
        <form className="glass-card flex flex-col gap-md" onSubmit={handleCreate}>
          <h3 className="font-semibold">New Webhook Endpoint</h3>
          <div className="grid-2">
            <div className="form-group">
              <label className="form-label">Name</label>
              <input type="text" className="form-input" value={formData.name} onChange={e => setFormData({...formData, name: e.target.value})} placeholder="Analytics System" required />
            </div>
            <div className="form-group">
              <label className="form-label">Payload URL</label>
              <input type="url" className="form-input" value={formData.url} onChange={e => setFormData({...formData, url: e.target.value})} placeholder="https://..." required />
            </div>
          </div>
          <div className="form-group">
            <label className="form-label">Events (comma separated)</label>
            <input type="text" className="form-input" value={formData.event_types} onChange={e => setFormData({...formData, event_types: e.target.value})} placeholder="user_registered, user_login" required />
          </div>
          <div className="flex justify-end gap-sm mt-sm">
            <button type="button" className="btn btn-secondary" onClick={() => setShowCreate(false)}>Cancel</button>
            <button type="submit" className="btn btn-primary">Create</button>
          </div>
        </form>
      )}

      <div className="glass-card p-0" style={{ overflow: 'hidden' }}>
        <table className="data-table">
          <thead>
            <tr>
              <th>Name / URL</th>
              <th>Events</th>
              <th>Status</th>
              <th style={{ width: '80px', textAlign: 'center' }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {webhooks.length === 0 ? (
              <tr><td colSpan={4} style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-secondary)' }}>No webhooks configured.</td></tr>
            ) : (
              webhooks.map(w => (
                <tr key={w.id}>
                  <td>
                    <div className="font-medium">{w.name}</div>
                    <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>{w.url}</div>
                  </td>
                  <td>
                    <div className="flex gap-sm flex-wrap">
                      {w.event_types.map((evt: string, i: number) => (
                        <span key={i} className="badge badge-purple" style={{ fontSize: '0.7rem' }}>{evt}</span>
                      ))}
                    </div>
                  </td>
                  <td>{w.is_active ? <span className="badge badge-green">Active</span> : <span className="badge badge-gray">Disabled</span>}</td>
                  <td>
                    <button className="btn btn-icon" style={{ color: '#ef4444' }} onClick={() => handleDelete(w.id)}>
                      <Trash2 size={18} />
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <h3 className="text-lg font-bold mt-lg flex align-center gap-sm">
        <Activity size={20} className="text-primary" /> Recent Deliveries
      </h3>
      <div className="glass-card p-0" style={{ overflow: 'hidden' }}>
        <table className="data-table">
          <thead>
            <tr>
              <th>Event</th>
              <th>Status Code</th>
              <th>Duration</th>
              <th>Date</th>
            </tr>
          </thead>
          <tbody>
            {deliveries.length === 0 ? (
              <tr><td colSpan={4} style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-secondary)' }}>No deliveries yet.</td></tr>
            ) : (
              deliveries.map(d => (
                <tr key={d.id}>
                  <td className="font-medium">{d.event_type}</td>
                  <td>
                    <span className={`badge ${d.success ? 'badge-green' : 'badge-red'}`}>
                      {d.status_code || 'Err'}
                    </span>
                  </td>
                  <td>{d.duration_ms} ms</td>
                  <td style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
                    {new Date(d.created_at).toLocaleString()}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};
