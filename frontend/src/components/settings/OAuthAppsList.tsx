import React, { useState, useEffect, useCallback } from 'react';
import { Key, Plus, Trash2, Copy, CheckCircle, AlertCircle } from 'lucide-react';
import { api } from '../../services/api';

export const OAuthAppsList: React.FC = () => {
  const [apps, setApps] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  
  const [showCreate, setShowCreate] = useState(false);
  const [newAppName, setNewAppName] = useState('');
  const [newAppRedirects, setNewAppRedirects] = useState('');
  
  const [newAppSecret, setNewAppSecret] = useState<string | null>(null);
  const [newAppId, setNewAppId] = useState<string | null>(null);

  const fetchApps = useCallback(async () => {
    try {
      setLoading(true);
      const resp = await api.get('/api/v1/organizations/oauth-apps');
      setApps(resp.data || []);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch OAuth apps');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchApps();
  }, [fetchApps]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newAppName.trim()) return;
    try {
      const resp = await api.post('/api/v1/organizations/oauth-apps', {
        name: newAppName,
        redirect_uris: newAppRedirects,
        client_type: 'confidential',
        allowed_scopes: 'read write'
      });
      setNewAppId(resp.data.client_id);
      setNewAppSecret(resp.data.raw_secret);
      setNewAppName('');
      setNewAppRedirects('');
      setShowCreate(false);
      fetchApps();
    } catch (err: any) {
      setError(err.message || 'Failed to create app');
    }
  };

  const handleDelete = async (id: string) => {
    if (!window.confirm('Are you sure you want to delete this application?')) return;
    try {
      await api.delete(`/api/v1/organizations/oauth-apps/${id}`);
      fetchApps();
    } catch (err: any) {
      setError(err.message || 'Failed to delete app');
    }
  };

  if (loading) return <div>Loading applications...</div>;

  return (
    <div className="flex flex-col gap-lg">
      <div className="flex justify-between align-center">
        <div>
          <h2 className="text-xl font-bold">OAuth Applications</h2>
          <p style={{ color: 'var(--text-secondary)' }}>Manage Machine-to-Machine (M2M) and standard OAuth clients.</p>
        </div>
        <button className="btn btn-primary" onClick={() => setShowCreate(!showCreate)}>
          <Plus size={18} />
          Create App
        </button>
      </div>

      {error && (
        <div className="alert alert-error">
          <AlertCircle size={20} />
          <span>{error}</span>
        </div>
      )}

      {newAppSecret && (
        <div className="alert alert-success" style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start', gap: '0.5rem' }}>
          <div className="flex align-center gap-sm">
            <CheckCircle size={20} />
            <strong>Application Created!</strong>
          </div>
          <p>Please copy your new Client ID and Client Secret. You will not be able to see the secret again.</p>
          <div style={{ background: 'rgba(0,0,0,0.2)', padding: '1rem', borderRadius: '4px', width: '100%', fontFamily: 'monospace' }}>
            <div><strong>Client ID:</strong> {newAppId}</div>
            <div><strong>Client Secret:</strong> {newAppSecret}</div>
          </div>
          <button className="btn btn-secondary btn-sm" onClick={() => { setNewAppSecret(null); setNewAppId(null); }}>
            I have copied these
          </button>
        </div>
      )}

      {showCreate && (
        <form className="glass-card flex flex-col gap-md" onSubmit={handleCreate}>
          <h3 className="font-semibold">New Application</h3>
          <div className="form-group">
            <label className="form-label">Application Name</label>
            <input 
              type="text" 
              className="form-input" 
              value={newAppName} 
              onChange={e => setNewAppName(e.target.value)} 
              placeholder="Backend Service App" 
              required 
            />
          </div>
          <div className="form-group">
            <label className="form-label">Allowed Callback URLs (Comma separated)</label>
            <input 
              type="text" 
              className="form-input" 
              value={newAppRedirects} 
              onChange={e => setNewAppRedirects(e.target.value)} 
              placeholder="https://app.example.com/callback" 
            />
          </div>
          <div className="flex justify-end gap-sm">
            <button type="button" className="btn btn-secondary" onClick={() => setShowCreate(false)}>Cancel</button>
            <button type="submit" className="btn btn-primary">Create</button>
          </div>
        </form>
      )}

      <div className="glass-card p-0" style={{ overflow: 'hidden' }}>
        <table className="data-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Client ID</th>
              <th>Type</th>
              <th style={{ width: '80px', textAlign: 'center' }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {apps.length === 0 ? (
              <tr>
                <td colSpan={4} style={{ textAlign: 'center', color: 'var(--text-secondary)', padding: '2rem' }}>
                  No OAuth applications created yet.
                </td>
              </tr>
            ) : (
              apps.map(app => (
                <tr key={app.id}>
                  <td className="font-medium">{app.name}</td>
                  <td><code style={{ fontSize: '0.8rem', background: 'var(--bg-main)', padding: '0.2rem 0.4rem', borderRadius: '4px' }}>{app.client_id}</code></td>
                  <td><span className="badge badge-purple">{app.client_type}</span></td>
                  <td>
                    <button 
                      className="btn btn-icon" 
                      style={{ color: '#ef4444' }} 
                      onClick={() => handleDelete(app.id)}
                      title="Delete Application"
                    >
                      <Trash2 size={18} />
                    </button>
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
