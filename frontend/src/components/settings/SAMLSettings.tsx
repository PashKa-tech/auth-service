import React, { useState, useEffect, useCallback } from 'react';
import { Network, Plus, Trash2, AlertCircle } from 'lucide-react';
import { api } from '../../services/api';

interface SAMLConnection {
  id: string;
  name: string;
  idp_entity_id: string;
  is_active: boolean;
}

export const SAMLSettings: React.FC = () => {
  const [connections, setConnections] = useState<SAMLConnection[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  
  const [showCreate, setShowCreate] = useState(false);
  const [formData, setFormData] = useState({
    name: '',
    idp_entity_id: '',
    sso_url: '',
    x509_cert: '',
    email_attribute: 'email',
    auto_provision: true
  });

  const fetchConnections = useCallback(async () => {
    try {
      setLoading(true);
      const resp = await api.get('/api/v1/organizations/saml-connections');
      setConnections(resp.data || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch SAML connections');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchConnections();
  }, [fetchConnections]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.name.trim() || !formData.sso_url.trim()) return;
    try {
      await api.post('/api/v1/organizations/saml-connections', formData);
      setFormData({
        name: '',
        idp_entity_id: '',
        sso_url: '',
        x509_cert: '',
        email_attribute: 'email',
        auto_provision: true
      });
      setShowCreate(false);
      fetchConnections();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create SAML connection');
    }
  };

  const handleDelete = async (id: string) => {
    if (!window.confirm('Are you sure you want to delete this SAML connection? Users relying on it will no longer be able to log in.')) return;
    try {
      await api.delete(`/api/v1/organizations/saml-connections/${id}`);
      fetchConnections();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete connection');
    }
  };

  if (loading) return <div>Loading SAML connections...</div>;

  return (
    <div className="flex flex-col gap-lg">
      <div className="flex justify-between align-center">
        <div>
          <h2 className="text-xl font-bold">Enterprise Connections (SAML 2.0)</h2>
          <p style={{ color: 'var(--text-secondary)' }}>Configure SAML Identity Providers like Okta, Azure AD, or Google Workspace.</p>
        </div>
        <button className="btn btn-primary" onClick={() => setShowCreate(!showCreate)}>
          <Plus size={18} />
          Add Connection
        </button>
      </div>

      {error && (
        <div className="alert alert-error">
          <AlertCircle size={20} />
          <span>{error}</span>
        </div>
      )}

      {showCreate && (
        <form className="glass-card flex flex-col gap-md" onSubmit={handleCreate}>
          <h3 className="font-semibold">New SAML Connection</h3>
          
          <div className="form-group">
            <label className="form-label">Connection Name</label>
            <input type="text" className="form-input" value={formData.name} onChange={e => setFormData({...formData, name: e.target.value})} placeholder="e.g. Okta Primary" required />
          </div>
          
          <div className="grid-2">
            <div className="form-group">
              <label className="form-label">IdP Entity ID</label>
              <input type="text" className="form-input" value={formData.idp_entity_id} onChange={e => setFormData({...formData, idp_entity_id: e.target.value})} placeholder="http://www.okta.com/exk..." required />
            </div>
            <div className="form-group">
              <label className="form-label">Sign In URL (SSO URL)</label>
              <input type="url" className="form-input" value={formData.sso_url} onChange={e => setFormData({...formData, sso_url: e.target.value})} placeholder="https://company.okta.com/app/..." required />
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">X509 Certificate (PEM Format)</label>
            <textarea className="form-input" rows={6} value={formData.x509_cert} onChange={e => setFormData({...formData, x509_cert: e.target.value})} placeholder="-----BEGIN CERTIFICATE-----..." required style={{ fontFamily: 'monospace' }} />
          </div>

          <div className="form-group">
            <label className="form-label">Email Attribute mapping</label>
            <input type="text" className="form-input" value={formData.email_attribute} onChange={e => setFormData({...formData, email_attribute: e.target.value})} placeholder="email" />
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
              <th>Name</th>
              <th>IdP Entity ID</th>
              <th>Status</th>
              <th style={{ width: '80px', textAlign: 'center' }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {connections.length === 0 ? (
              <tr>
                <td colSpan={4} style={{ textAlign: 'center', color: 'var(--text-secondary)', padding: '2rem' }}>
                  No SAML connections configured.
                </td>
              </tr>
            ) : (
              connections.map(c => (
                <tr key={c.id}>
                  <td className="font-medium flex align-center gap-sm">
                    <Network size={16} className="text-secondary" />
                    {c.name}
                  </td>
                  <td style={{ maxWidth: '200px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{c.idp_entity_id}</td>
                  <td>
                    {c.is_active ? <span className="badge badge-green">Active</span> : <span className="badge badge-gray">Disabled</span>}
                  </td>
                  <td>
                    <button className="btn btn-icon" style={{ color: '#ef4444' }} onClick={() => handleDelete(c.id)}>
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
