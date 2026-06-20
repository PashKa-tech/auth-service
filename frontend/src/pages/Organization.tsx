import React, { useState, useEffect, useCallback } from 'react';
import { Building2, Key, Trash2, Plus, AlertCircle, CheckCircle, Copy, Users, Mail } from 'lucide-react';
import { api } from '../services/api';
import { motion } from 'framer-motion';

export const Organization: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'api' | 'team'>('api');
  const [org, setOrg] = useState<any>(null);
  const [apiKeys, setApiKeys] = useState<any[]>([]);
  const [members, setMembers] = useState<any[]>([]);
  const [invites, setInvites] = useState<any[]>([]);
  
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  
  // API Key State
  const [newKeyName, setNewKeyName] = useState('');
  const [newSecret, setNewSecret] = useState<string | null>(null);

  // Invite State
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteRole, setInviteRole] = useState('user');

  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      const orgResp = await api.get('/api/v1/organizations/current');
      setOrg(orgResp.data);

      try {
        const [keysResp, membersResp, invitesResp] = await Promise.all([
          api.get('/api/v1/organizations/api-keys'),
          api.get('/api/v1/organizations/members'),
          api.get('/api/v1/organizations/invites')
        ]);
        setApiKeys(keysResp.data || []);
        setMembers(membersResp.data || []);
        setInvites(invitesResp.data || []);
      } catch (err: any) {
        if (err.response?.status !== 403) {
          throw err;
        }
        // If 403, user is not admin, ignore
      }
    } catch (err: any) {
      setError(err.message || 'Failed to load organization data');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const showSuccess = (msg: string) => {
    setSuccess(msg);
    setTimeout(() => setSuccess(''), 4000);
  };

  const handleCreateKey = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newKeyName.trim()) return;

    setError('');
    setNewSecret(null);
    setActionLoading('create-key');

    try {
      const resp = await api.post('/api/v1/organizations/api-keys', { name: newKeyName });
      setNewSecret(resp.data.raw_secret);
      showSuccess('API Key created successfully!');
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
    setActionLoading(`revoke-key-${id}`);

    try {
      await api.delete(`/api/v1/organizations/api-keys/${id}`);
      showSuccess('API Key revoked successfully.');
      await fetchData();
    } catch (err: any) {
      setError(err.message || 'Failed to revoke API key');
    } finally {
      setActionLoading(null);
    }
  };

  const handleSendInvite = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inviteEmail.trim()) return;

    setError('');
    setActionLoading('send-invite');

    try {
      await api.post('/api/v1/organizations/invites', { email: inviteEmail, role: inviteRole });
      showSuccess('Invitation sent successfully!');
      setInviteEmail('');
      await fetchData();
    } catch (err: any) {
      setError(err.message || 'Failed to send invitation');
    } finally {
      setActionLoading(null);
    }
  };

  const handleRevokeInvite = async (id: string) => {
    setError('');
    setActionLoading(`revoke-invite-${id}`);
    try {
      await api.delete(`/api/v1/organizations/invites/${id}`);
      showSuccess('Invitation revoked.');
      await fetchData();
    } catch (err: any) {
      setError(err.message || 'Failed to revoke invite');
    } finally {
      setActionLoading(null);
    }
  };

  const handleRemoveMember = async (id: string) => {
    if (!window.confirm("Are you sure you want to remove this member?")) return;
    setError('');
    setActionLoading(`remove-member-${id}`);
    try {
      await api.delete(`/api/v1/organizations/members/${id}`);
      showSuccess('Member removed.');
      await fetchData();
    } catch (err: any) {
      setError(err.message || 'Failed to remove member');
    } finally {
      setActionLoading(null);
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    showSuccess('Copied to clipboard!');
  };

  if (loading && !org) {
    return <div className="flex-center" style={{ minHeight: '50vh', color: 'var(--text-secondary)' }}>Loading organization...</div>;
  }

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Developer Settings</h1>
        <p className="page-subtitle">Manage your organization's API keys and team members</p>
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

      {/* Organization Info */}
      <motion.div className="glass-card" style={{ marginBottom: '2rem' }} whileHover={{ scale: 1.005 }}>
        <h2 style={{ fontSize: '1.25rem', marginBottom: '1.25rem', display: 'flex', alignItems: 'center', gap: '0.5rem', fontWeight: 500 }}>
          <Building2 size={20} /> Organization Details
        </h2>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1.5rem' }}>
          <div>
            <span style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Name</span>
            <p style={{ fontWeight: 500, fontSize: '1.1rem', marginTop: '0.25rem' }}>{org?.name || 'My Organization'}</p>
          </div>
          <div>
            <span style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Rate Limit</span>
            <p style={{ fontWeight: 500, marginTop: '0.25rem' }}><span className="badge badge-gray">{org?.rate_limit_rpm || 1000} req/min</span></p>
          </div>
          <div>
            <span style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Created</span>
            <p style={{ fontWeight: 500, marginTop: '0.25rem', color: 'var(--text-primary)' }}>
              {org?.created_at ? new Date(org.created_at).toLocaleDateString() : 'Unknown'}
            </p>
          </div>
        </div>
      </motion.div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: '1rem', borderBottom: '1px solid var(--border-glass)', marginBottom: '1.5rem', paddingBottom: '0.5rem' }}>
        <button
          onClick={() => setActiveTab('api')}
          className="btn"
          style={{
            background: 'transparent',
            border: 'none',
            borderBottom: activeTab === 'api' ? '2px solid var(--primary-color)' : '2px solid transparent',
            color: activeTab === 'api' ? 'var(--text-primary)' : 'var(--text-secondary)',
            padding: '0.5rem 1rem',
            borderRadius: '0',
            fontWeight: 500
          }}
        >
          <Key size={16} /> API Keys
        </button>
        <button
          onClick={() => setActiveTab('team')}
          className="btn"
          style={{
            background: 'transparent',
            border: 'none',
            borderBottom: activeTab === 'team' ? '2px solid var(--primary-color)' : '2px solid transparent',
            color: activeTab === 'team' ? 'var(--text-primary)' : 'var(--text-secondary)',
            padding: '0.5rem 1rem',
            borderRadius: '0',
            fontWeight: 500
          }}
        >
          <Users size={16} /> Team
        </button>
      </div>

      {/* API Keys Tab */}
      {activeTab === 'api' && (
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="flex flex-col gap-lg">
          <div className="glass-card">
            <h2 style={{ fontSize: '1.1rem', marginBottom: '0.5rem', fontWeight: 500 }}>Active API Keys</h2>
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
              <button type="submit" className="btn btn-primary" disabled={actionLoading === 'create-key'}>
                <Plus size={16} /> {actionLoading === 'create-key' ? 'Generating...' : 'Create Key'}
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
                        disabled={actionLoading === `revoke-key-${key.id}`}
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
          </div>
        </motion.div>
      )}

      {/* Team Tab */}
      {activeTab === 'team' && (
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="flex flex-col gap-lg">
          
          <div className="glass-card">
            <h2 style={{ fontSize: '1.1rem', marginBottom: '0.5rem', fontWeight: 500 }}>Invite Member</h2>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginBottom: '1.5rem' }}>
              Invite colleagues to join your organization.
            </p>

            <form onSubmit={handleSendInvite} style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
              <input
                type="email"
                placeholder="colleague@example.com"
                className="form-input"
                value={inviteEmail}
                onChange={(e) => setInviteEmail(e.target.value)}
                style={{ flexGrow: 1, minWidth: '200px' }}
                required
              />
              <select 
                className="form-input" 
                value={inviteRole} 
                onChange={(e) => setInviteRole(e.target.value)}
                style={{ width: 'auto' }}
              >
                <option value="user">User</option>
                <option value="admin">Admin</option>
              </select>
              <button type="submit" className="btn btn-primary" disabled={actionLoading === 'send-invite'}>
                <Mail size={16} /> {actionLoading === 'send-invite' ? 'Sending...' : 'Send Invite'}
              </button>
            </form>
          </div>

          {/* Pending Invites */}
          {invites.length > 0 && (
            <div className="glass-card">
              <h2 style={{ fontSize: '1.1rem', marginBottom: '1rem', fontWeight: 500 }}>Pending Invites</h2>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                {invites.map(inv => (
                  <div key={inv.id} className="flex justify-between align-center" style={{ padding: '0.75rem', background: 'rgba(255,255,255,0.02)', border: '1px solid var(--border-glass)', borderRadius: '8px' }}>
                    <div>
                      <p style={{ fontWeight: 500, fontSize: '0.95rem' }}>{inv.email}</p>
                      <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Role: {inv.role} • Expires: {new Date(inv.expires_at).toLocaleDateString()}</p>
                    </div>
                    <button
                      onClick={() => handleRevokeInvite(inv.id)}
                      className="btn btn-secondary"
                      style={{ padding: '0.3rem 0.6rem', fontSize: '0.75rem' }}
                      disabled={actionLoading === `revoke-invite-${inv.id}`}
                    >
                      Revoke
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Members List */}
          <div className="glass-card">
            <h2 style={{ fontSize: '1.1rem', marginBottom: '1rem', fontWeight: 500 }}>Organization Members</h2>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              {members.map(member => (
                <div key={member.id} className="flex justify-between align-center" style={{ padding: '0.75rem', background: 'transparent', border: '1px solid var(--border-glass)', borderRadius: '8px' }}>
                  <div className="flex align-center gap-md">
                    <div style={{ width: '32px', height: '32px', borderRadius: '50%', background: 'var(--primary-color)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff', fontWeight: 'bold' }}>
                      {member.email[0].toUpperCase()}
                    </div>
                    <div>
                      <p style={{ fontWeight: 500, fontSize: '0.95rem' }}>{member.email}</p>
                      <span className={`badge ${member.role === 'admin' ? 'badge-purple' : 'badge-gray'}`} style={{ marginTop: '0.25rem' }}>
                        {member.role}
                      </span>
                    </div>
                  </div>
                  <button
                    onClick={() => handleRemoveMember(member.id)}
                    className="btn btn-secondary"
                    style={{ padding: '0.4rem', color: 'var(--danger-color)', borderColor: 'rgba(239, 68, 68, 0.3)' }}
                    disabled={actionLoading === `remove-member-${member.id}`}
                    title="Remove member"
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              ))}
            </div>
          </div>

        </motion.div>
      )}

    </div>
  );
};

