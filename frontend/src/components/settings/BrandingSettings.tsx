import React, { useState, useEffect } from 'react';
import { Save, AlertCircle, CheckCircle } from 'lucide-react';
import { api } from '../../services/api';

export const BrandingSettings: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  
  const [formData, setFormData] = useState({
    name: '',
    logo_url: '',
    primary_color: '#8b5cf6',
    font_family: 'Inter, sans-serif'
  });

  const fetchBranding = async () => {
    try {
      setLoading(true);
      const orgResp = await api.get('/api/v1/organizations/current');
      const tenantId = orgResp.data.id;
      const brandResp = await api.get(`/api/v1/organizations/${tenantId}/branding`);
      if (brandResp.data) {
        setFormData({
          name: brandResp.data.name || '',
          logo_url: brandResp.data.logo_url || '',
          primary_color: brandResp.data.primary_color || '#8b5cf6',
          font_family: brandResp.data.font_family || 'Inter, sans-serif'
        });
      }
    } catch (err: any) {
      setError(err.message || 'Failed to load branding settings');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchBranding();
  }, []);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError('');
    setSuccess('');
    try {
      await api.put('/api/v1/organizations/current/settings', formData);
      setSuccess('Branding settings saved successfully');
      setTimeout(() => setSuccess(''), 3000);
    } catch (err: any) {
      setError(err.message || 'Failed to save branding settings');
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <div>Loading branding settings...</div>;

  return (
    <div className="glass-card">
      <h2 className="text-xl font-bold mb-lg">Branding Customization</h2>
      <p style={{ color: 'var(--text-secondary)', marginBottom: '1.5rem' }}>
        Customize the appearance of your login pages and emails.
      </p>

      {error && (
        <div className="alert alert-error mb-lg">
          <AlertCircle size={20} />
          <span>{error}</span>
        </div>
      )}
      
      {success && (
        <div className="alert alert-success mb-lg" style={{ background: 'rgba(16, 185, 129, 0.1)', color: '#10b981', border: '1px solid rgba(16, 185, 129, 0.2)' }}>
          <CheckCircle size={20} />
          <span>{success}</span>
        </div>
      )}

      <form onSubmit={handleSave} className="flex flex-col gap-lg">
        <div className="form-group">
          <label className="form-label">Organization Name</label>
          <input
            type="text"
            className="form-input"
            value={formData.name}
            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
            placeholder="Acme Corp"
          />
        </div>

        <div className="form-group">
          <label className="form-label">Logo URL</label>
          <input
            type="url"
            className="form-input"
            value={formData.logo_url}
            onChange={(e) => setFormData({ ...formData, logo_url: e.target.value })}
            placeholder="https://example.com/logo.png"
          />
          {formData.logo_url && (
            <div style={{ marginTop: '0.5rem', padding: '1rem', background: 'var(--bg-elevated)', borderRadius: '0.5rem', display: 'inline-block' }}>
              <img src={formData.logo_url} alt="Logo Preview" style={{ maxHeight: '50px', maxWidth: '200px' }} onError={(e) => (e.currentTarget.style.display = 'none')} />
            </div>
          )}
        </div>

        <div className="grid-2">
          <div className="form-group">
            <label className="form-label">Primary Color</label>
            <div className="flex align-center gap-sm">
              <input
                type="color"
                value={formData.primary_color}
                onChange={(e) => setFormData({ ...formData, primary_color: e.target.value })}
                style={{ width: '40px', height: '40px', padding: '0', border: 'none', borderRadius: '4px', cursor: 'pointer' }}
              />
              <input
                type="text"
                className="form-input"
                value={formData.primary_color}
                onChange={(e) => setFormData({ ...formData, primary_color: e.target.value })}
                pattern="^#[0-9A-Fa-f]{6}$"
                style={{ flex: 1 }}
              />
            </div>
          </div>

          <div className="form-group">
            <label className="form-label">Font Family</label>
            <select
              className="form-input"
              value={formData.font_family}
              onChange={(e) => setFormData({ ...formData, font_family: e.target.value })}
            >
              <option value="Inter, sans-serif">Inter (Default)</option>
              <option value="Roboto, sans-serif">Roboto</option>
              <option value="Outfit, sans-serif">Outfit</option>
              <option value="system-ui, sans-serif">System UI</option>
            </select>
          </div>
        </div>

        <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '1rem' }}>
          <button type="submit" className="btn btn-primary" disabled={saving}>
            <Save size={18} />
            {saving ? 'Saving...' : 'Save Changes'}
          </button>
        </div>
      </form>
    </div>
  );
};
