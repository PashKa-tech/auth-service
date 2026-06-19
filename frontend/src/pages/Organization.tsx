import React, { useState, useEffect } from 'react';
import { Building2, Key, Trash2, Plus, AlertCircle, CheckCircle, Copy } from 'lucide-react';
import { api } from '../services/api';
import { motion } from 'framer-motion';

export const Organization: React.FC = () => {
  const [org, setOrg] = useState<any>(null);
  const [apiKeys, setApiKeys] = useState<any[]>([]);
  
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [newKeyName, setNewKeyName] = useState('');
  const [newSecret, setNewSecret] = useState<string | null>(null);

  const fetchData = async () => {
    try {
      setLoading(true);
      const orgResp = await api.get('/api/v1/organizations/current');
      setOrg(orgResp.data);

      try {
        const keysResp = await api.get('/api/v1/organizations/api-keys');
        setApiKeys(keysResp.data || []);
      } catch (err: any) {
        if (err.response?.status !== 403) {
          throw err;
        }
        // If 403, user is not admin, just don't show keys
      }
    } catch (err: any) {
      setError(err.message || 'Failed to load organization data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleCreateKey = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newKeyName.trim()) return;

    setError('');
    setSuccess('');
    setNewSecret(null);
    setActionLoading('create');

    try {
      const resp = await api.post('/api/v1/organizations/api-keys', { name: newKeyName });
      setNewSecret(resp.data.raw_secret);
      setSuccess('API Key created successfully!');
      setNewKeyName('');
      await fetchData();
    } catch (err: any) {
      setError(err.message || 'Failed to create API key');
    } finally {
      setActionLoading(null);
    }
  };

  const handleRevokeKey = async (id: string) => {
    setError('');
    setSuccess('');
    setActionLoading(`revoke-${id}`);

    try {
      await api.delete(`/api/v1/organizations/api-keys/${id}`);
      setSuccess('API Key revoked successfully.');
      await fetchData();
    } catch (err: any) {
      if (err.message?.includes('Step-up')) {
        setError('Step-up authentication required to revoke keys. Please log in again.');
      } else {
        setError(err.message || 'Failed to revoke API key');
      }
    } finally {
      setActionLoading(null);
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setSuccess('Copied to clipboard!');
    setTimeout(() => setSuccess(''), 3000);
  };

  if (loading) {
    return <div className="flex-center" style={{ minHeight: '50vh', color: 'var(--text-secondary)' }}>Loading organization...</div>;
  }

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Developer Settings</h1>
        <p className="page-subtitle">Manage your organization's API keys and integrations</p>
      </div>

      {error && (
        <div className="alert alert-error" style={{ marginBottom: '1.5rem' }}>
          <AlertCircle size={20} />
          <span>{error}</span>
        </div>
      )}
      {success && (
        <div className="alert alert-success" style={{ marginBottom: '1.5rem' }}>
          <CheckCircle size={20} />
          <span>{success}</span>
        </div>
      )}

      <div className="grid-2">
        {/* Organization Info */}
        <div className="flex flex-col gap-lg">
          <motion.div className="glass-card" whileHover={{ scale: 1.01 }}>
            <h2 style={{ fontSize: '1.25rem', marginBottom: '1.25rem', display: 'flex', alignItems: 'center', gap: '0.5rem', fontWeight: 500 }}>
              <Building2 size={20} /> Organization Details
            </h2>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <div>
                <span style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Name</span>
                <p style={{ fontWeight: 500, fontSize: '1.1rem' }}>{org?.name || 'My Organization'}</p>
              </div>
              <div>
                <span style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Rate Limit (RPM)</span>
                <p style={{ fontWeight: 500, marginTop: '0.25rem' }}><span className="badge badge-gray">{org?.rate_limit_rpm || 1000} req/min</span></p>
              </div>
              <div>
                <span style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Created</span>
                <p style={{ fontWeight: 500, marginTop: '0.25rem' }}>
                  {org?.created_at ? new Date(org.created_at).toLocaleDateString() : 'Unknown'}
                </p>
              </div>
            </div>
          </motion.div>
        </div>

        {/* API Keys */}
        <div className="flex flex-col gap-lg">
          <motion.div className="glass-card" whileHover={{ scale: 1.01 }}>
            <h2 style={{ fontSize: '1.25rem', marginBottom: '1.25rem', display: 'flex', alignItems: 'center', gap: '0.5rem', fontWeight: 500 }}>
              <Key size={20} /> API Keys
            </h2>
            
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginBottom: '1.5rem' }}>
              Use API keys to authenticate programmatic requests to our API. Keys carry the permissions of your organization.
            </p>

            {newSecret && (
              <div style={{ background: 'rgba(16, 185, 129, 0.1)', border: '1px solid var(--success)', padding: '1rem', borderRadius: '8px', marginBottom: '1.5rem' }}>
                <p style={{ fontWeight: 600, color: 'var(--success)', marginBottom: '0.5rem' }}>Save your new API Key!</p>
                <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '1rem' }}>
                  This is the only time it will be shown. If you lose it, you will need to generate a new one.
                </p>
                <div style={{ display: 'flex', gap: '0.5rem' }}>
                  <input type="text" readOnly value={newSecret} className="form-input" style={{ flexGrow: 1, fontFamily: 'monospace' }} />
                  <button onClick={() => copyToClipboard(newSecret)} className="btn btn-secondary">
                    <Copy size={16} />
                  </button>
                </div>
              </div>
            )}

            <form onSubmit={handleCreateKey} style={{ display: 'flex', gap: '0.5rem', marginBottom: '1.5rem' }}>
              <input
                type="text"
                placeholder="Key Name (e.g. Production Backend)"
                className="form-input"
                value={newKeyName}
                onChange={(e) => setNewKeyName(e.target.value)}
                style={{ flexGrow: 1 }}
                required
              />
              <button type="submit" className="btn btn-primary" disabled={actionLoading === 'create'}>
                <Plus size={16} /> {actionLoading === 'create' ? 'Generating...' : 'Create Key'}
              </button>
            </form>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              {apiKeys.length === 0 ? (
                <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>No API keys generated yet.</p>
              ) : (
                apiKeys.map((key) => (
                  <div key={key.id} style={{ padding: '1rem', background: 'transparent', border: '1px solid var(--border-glass)', borderRadius: '8px' }}>
                    <div className="flex justify-between align-center">
                      <span style={{ fontWeight: 500, fontSize: '0.95rem' }}>{key.name}</span>
                      <button
                        onClick={() => handleRevokeKey(key.id)}
                        className="btn btn-secondary"
                        style={{ padding: '0.3rem 0.6rem', fontSize: '0.75rem', borderColor: 'rgba(239, 68, 68, 0.3)', color: 'var(--text-primary)' }}
                        disabled={actionLoading === `revoke-${key.id}`}
                      >
                        <Trash2 size={12} style={{ display: 'inline', marginRight: '4px' }} /> Revoke
                      </button>
                    </div>
                    <p style={{ fontFamily: 'monospace', fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: '0.5rem' }}>
                      {key.key_prefix}****************
                    </p>
                    <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
                      Created on {new Date(key.created_at).toLocaleDateString()}
                    </p>
                  </div>
                ))
              )}
            </div>
          </motion.div>
        </div>
      </div>
    </div>
  );
};
