import React, { useState, useEffect, useCallback } from 'react';
import { ShieldCheck, Plus, Trash2, AlertCircle, Users } from 'lucide-react';
import { api } from '../../services/api';

export const RBACSettings: React.FC = () => {
  const [roles, setRoles] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  
  const [showCreate, setShowCreate] = useState(false);
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    permissions: ''
  });

  const fetchRoles = useCallback(async () => {
    try {
      setLoading(true);
      const resp = await api.get('/api/v1/rbac/roles');
      setRoles(resp.data || []);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch roles');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchRoles();
  }, [fetchRoles]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.name.trim()) return;
    try {
      const perms = formData.permissions.split(',').map(p => p.trim()).filter(p => p);
      await api.post('/api/v1/rbac/roles', {
        name: formData.name,
        description: formData.description,
        permissions: perms
      });
      setFormData({ name: '', description: '', permissions: '' });
      setShowCreate(false);
      fetchRoles();
    } catch (err: any) {
      setError(err.message || 'Failed to create role');
    }
  };

  const handleDelete = async (id: string) => {
    if (!window.confirm('Are you sure you want to delete this role?')) return;
    try {
      await api.delete(`/api/v1/rbac/roles/${id}`);
      fetchRoles();
    } catch (err: any) {
      setError(err.message || 'Failed to delete role');
    }
  };

  if (loading) return <div>Loading roles...</div>;

  return (
    <div className="flex flex-col gap-lg">
      <div className="flex justify-between align-center">
        <div>
          <h2 className="text-xl font-bold">Roles & Permissions</h2>
          <p style={{ color: 'var(--text-secondary)' }}>Manage custom roles and assign them to users.</p>
        </div>
        <button className="btn btn-primary" onClick={() => setShowCreate(!showCreate)}>
          <Plus size={18} />
          Create Role
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
          <h3 className="font-semibold">New Custom Role</h3>
          <div className="grid-2">
            <div className="form-group">
              <label className="form-label">Role Name</label>
              <input type="text" className="form-input" value={formData.name} onChange={e => setFormData({...formData, name: e.target.value})} placeholder="Billing Admin" required />
            </div>
            <div className="form-group">
              <label className="form-label">Description</label>
              <input type="text" className="form-input" value={formData.description} onChange={e => setFormData({...formData, description: e.target.value})} placeholder="Can access billing portal" />
            </div>
          </div>
          <div className="form-group">
            <label className="form-label">Permissions (comma separated)</label>
            <input type="text" className="form-input" value={formData.permissions} onChange={e => setFormData({...formData, permissions: e.target.value})} placeholder="read:invoices, write:payment_methods" />
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
              <th>Role</th>
              <th>Permissions</th>
              <th>Type</th>
              <th style={{ width: '80px', textAlign: 'center' }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {roles.length === 0 ? (
              <tr><td colSpan={4} style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-secondary)' }}>No roles found.</td></tr>
            ) : (
              roles.map(r => (
                <tr key={r.id}>
                  <td>
                    <div className="font-medium flex align-center gap-sm">
                      <ShieldCheck size={16} className="text-secondary" />
                      {r.name}
                    </div>
                    {r.description && <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>{r.description}</div>}
                  </td>
                  <td>
                    <div className="flex gap-sm flex-wrap">
                      {r.permissions?.length > 0 ? r.permissions.map((p: string, i: number) => (
                        <span key={i} className="badge badge-purple" style={{ fontSize: '0.7rem' }}>{p}</span>
                      )) : <span className="text-secondary" style={{ fontSize: '0.8rem' }}>None</span>}
                    </div>
                  </td>
                  <td>{r.is_system ? <span className="badge badge-gray">System</span> : <span className="badge badge-green">Custom</span>}</td>
                  <td>
                    {!r.is_system && (
                      <button className="btn btn-icon" style={{ color: '#ef4444' }} onClick={() => handleDelete(r.id)}>
                        <Trash2 size={18} />
                      </button>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
      
      {/* TODO: We can add an Assign Role section here to map users to roles */}
      <div className="glass-card">
        <h3 className="font-semibold mb-sm flex align-center gap-sm">
          <Users size={18} className="text-primary" /> Assign Roles
        </h3>
        <p className="text-secondary mb-md">Use the API (`POST /api/v1/rbac/roles/assign`) or build a user search dropdown here to assign these custom roles to specific users.</p>
      </div>
    </div>
  );
};
