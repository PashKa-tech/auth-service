import React, { useState, useEffect } from 'react';
import { Shield, Smartphone, Trash2, Link2, Unlink, CheckCircle, AlertCircle, RefreshCw, Layers, Key, History, Activity, Monitor, Laptop, MapPin, Server } from 'lucide-react';
import { api, API_BASE_URL } from '../services/api';
import { QRCodeSVG } from 'qrcode.react';
import { motion } from 'framer-motion';

export const Profile: React.FC = () => {
  const [user, setUser] = useState<any>(null);
  const [sessions, setSessions] = useState<any[]>([]);
  const [auditLogs, setAuditLogs] = useState<any[]>([]);
  const [linkedAccounts, setLinkedAccounts] = useState<any[]>([]);
  
  // Status/Error state
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  // 2FA state
  const [mfaSetupData, setMfaSetupData] = useState<any>(null);
  const [totpVerificationCode, setTotpVerificationCode] = useState('');
  const [disablingMfa, setDisablingMfa] = useState(false);
  const [disableCredential, setDisableCredential] = useState('');
  const [disableMethod, setDisableMethod] = useState<'password' | 'totp'>('totp');

  const fetchData = async () => {
    try {
      const meResp = await api.get('/api/v1/auth/me');
      setUser(meResp.data);

      const sessResp = await api.get('/api/v1/auth/sessions');
      setSessions(sessResp.data);

      const oauthResp = await api.get('/api/v1/auth/me/linked-accounts');
      setLinkedAccounts(oauthResp.data);

      const auditResp = await api.get('/api/v1/auth/me/audit');
      setAuditLogs(auditResp.data);
    } catch (err: any) {
      setError(err.message || 'Failed to load profile data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleLogoutAllOther = async () => {
    setError('');
    setSuccess('');
    setActionLoading('logoutAll');
    try {
      await api.post('/api/v1/auth/logout-all');
      // Backend revoked ALL sessions and cleared our cookie.
      // We must reload the page so the app re-initializes and redirects to login.
      window.location.href = '/login';
    } catch (err: any) {
      setError(err.message || 'Failed to logout from other sessions');
      setActionLoading(null);
    }
  };

  const handleRevokeSession = async (sessionId: string) => {
    setError('');
    setSuccess('');
    setActionLoading(`revoke-${sessionId}`);
    try {
      await api.delete(`/api/v1/auth/sessions/${sessionId}`);
      setSuccess('Session revoked successfully.');
      await fetchData();
    } catch (err: any) {
      if (err.message?.includes('Step-up')) {
        setError('Step-up authentication required to revoke specific sessions. Please log in again to verify your identity.');
      } else {
        setError(err.message || 'Failed to revoke session');
      }
    } finally {
      setActionLoading(null);
    }
  };

  const handleLinkAccount = (provider: string) => {
    setError('');
    setSuccess('');
    const clientState = window.location.origin + '/profile';
    const linkUrl = `${API_BASE_URL}/api/v1/auth/oauth/${provider}?state=${encodeURIComponent(clientState)}`;
    window.location.href = linkUrl;
  };

  const handleUnlinkAccount = async (provider: string) => {
    setError('');
    setSuccess('');
    setActionLoading(`unlink-${provider}`);
    try {
      await api.delete(`/api/v1/auth/me/linked-accounts/${provider}`);
      setSuccess(`Account ${provider} unlinked successfully.`);
      await fetchData();
    } catch (err: any) {
      setError(err.message || 'Failed to unlink account');
    } finally {
      setActionLoading(null);
    }
  };

  const handleStart2faSetup = async () => {
    setError('');
    setSuccess('');
    setActionLoading('start2fa');
    try {
      const resp = await api.post('/api/v1/auth/2fa/setup');
      setMfaSetupData(resp.data);
    } catch (err: any) {
      setError(err.message || 'Failed to initialize 2FA');
    } finally {
      setActionLoading(null);
    }
  };

  const handleConfirm2fa = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setSuccess('');
    try {
      await api.post('/api/v1/auth/2fa/confirm-setup', {
        totp_code: totpVerificationCode,
      });
      setSuccess('Two-factor authentication (2FA) enabled successfully.');
      setMfaSetupData(null);
      setTotpVerificationCode('');
      fetchData();
    } catch (err: any) {
      setError(err.message || 'Invalid TOTP verification code');
    }
  };

  const handleDisable2fa = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setSuccess('');
    try {
      const body: any = {};
      if (disableMethod === 'totp') {
        body.totp_code = disableCredential;
      } else {
        body.password = disableCredential;
      }

      await api.post('/api/v1/auth/2fa/disable', body);
      setSuccess('2FA successfully disabled!');
      setMfaSetupData(null);
      setTotpVerificationCode('');
      await fetchData();
    } catch (err: any) {
      setError(err.message || 'Failed to disable 2FA');
    }
  };

  const handleRegenerateBackupCodes = async () => {
    setError('');
    setSuccess('');
    try {
      const resp = await api.post('/api/v1/auth/2fa/backup-codes/regenerate');
      setMfaSetupData({
        backup_codes: resp.data.backup_codes,
        secret: 'Regeneration requested',
        qr_code_uri: null,
      });
      setSuccess('New backup codes generated. Please save them securely!');
    } catch (err: any) {
      setError(err.message || 'Failed to regenerate backup codes');
    }
  };

  const handleRegisterPasskey = async () => {
    setError('');
    setSuccess('');
    setActionLoading('registerPasskey');
    try {
      // 1. Get options
      const beginResp = await api.post('/api/v1/auth/webauthn/register/begin');
      
      // 2. Start registration
      const { startRegistration } = await import('@simplewebauthn/browser');
      let asseResp;
      try {
        asseResp = await startRegistration({ optionsJSON: beginResp.data });
      } catch (e: any) {
        throw new Error('Biometric registration cancelled or failed');
      }

      // 3. Complete
      const deviceName = window.prompt("Enter a name for this Passkey device:", "My Device");
      await api.post('/api/v1/auth/webauthn/register/complete', {
        response: asseResp,
        name: deviceName || 'New Passkey'
      });

      setSuccess('Passkey added successfully!');
      await fetchData();
    } catch (err: any) {
      setError(err.message || 'Failed to register Passkey');
    } finally {
      setActionLoading(null);
    }
  };

  if (loading) {
    return <div className="flex-center" style={{ minHeight: '50vh', color: 'var(--text-secondary)' }}>Loading profile...</div>;
  }

  const isMfaEnabled = user?.two_factor_enabled || false;
  const allProviders = ['google', 'github', 'discord', 'apple', 'facebook', 'twitter', 'amazon'];

  return (
    <div>
      {/* Page Header */}
      <div className="page-header">
        <h1 className="page-title">Profile Settings</h1>
        <p className="page-subtitle">Manage account security, active sessions, and linked social accounts</p>
      </div>

      {/* Alert Banners */}
      {error && (
        <div className="alert alert-error" role="alert" aria-live="assertive">
          <AlertCircle size={20} />
          <span>{error}</span>
        </div>
      )}
      {success && (
        <div className="alert alert-success" role="status" aria-live="polite">
          <CheckCircle size={20} />
          <span>{success}</span>
        </div>
      )}

      <div className="grid-2">
        {/* Left Column: Security Settings */}
        <div className="flex flex-col gap-lg">
          
          {/* User Info Card */}
          <motion.div className="glass-card" whileHover={{ scale: 1.01 }}>
            <h2 style={{ fontSize: '1.25rem', marginBottom: '1.25rem', display: 'flex', alignItems: 'center', gap: '0.5rem', fontWeight: 500 }}>
              <Smartphone size={20} /> Account Information
            </h2>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <div>
                <span style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Email</span>
                <p style={{ fontWeight: 500, fontSize: '1.1rem' }}>{user?.email}</p>
              </div>
              <div>
                <span style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Role</span>
                <p style={{ fontWeight: 500, marginTop: '0.25rem' }}><span className="badge badge-purple">{user?.role}</span></p>
              </div>
              <div>
                <span style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Status</span>
                <p style={{ fontWeight: 500, marginTop: '0.25rem' }}>
                  <span className={user?.is_active ? 'badge badge-green' : 'badge badge-red'}>
                    {user?.is_active ? 'Active' : 'Disabled'}
                  </span>
                </p>
              </div>
            </div>
          </motion.div>

          {/* 2FA Card */}
          <motion.div className="glass-card" whileHover={{ scale: 1.01 }}>
            <h2 style={{ fontSize: '1.25rem', marginBottom: '1.25rem', display: 'flex', alignItems: 'center', gap: '0.5rem', fontWeight: 500 }}>
              <Shield size={20} /> Two-Factor Authentication (2FA)
            </h2>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.5rem' }}>
              <div>
                <p style={{ fontWeight: 500 }}>Authenticator App</p>
                <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
                  {isMfaEnabled 
                    ? 'Your account is securely protected.' 
                    : 'Add an extra layer of security.'}
                </p>
              </div>
              <span className={isMfaEnabled ? 'badge badge-green' : 'badge badge-red'}>
                {isMfaEnabled ? 'Enabled' : 'Disabled'}
              </span>
            </div>

            {/* If 2FA is not enabled and setup is not in progress */}
            {!isMfaEnabled && !mfaSetupData && (
              <button onClick={handleStart2faSetup} className="btn btn-primary" style={{ width: '100%' }} disabled={actionLoading === 'start2fa'}>
                {actionLoading === 'start2fa' ? 'Loading...' : 'Setup 2FA (TOTP)'}
              </button>
            )}

            {/* If 2FA Setup is in progress */}
            {mfaSetupData && !isMfaEnabled && (
              <div style={{ marginTop: '1.5rem', borderTop: '1px solid var(--border-glass)', paddingTop: '1.5rem' }}>
                <h3 style={{ fontSize: '1.1rem', marginBottom: '0.5rem', fontWeight: 500 }}>1. Scan QR Code</h3>
                <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', marginBottom: '1rem' }}>
                  Use Google Authenticator, Authy, or any TOTP app to scan:
                </p>
                {mfaSetupData.qr_code_uri && (
                  <div style={{ textAlign: 'center' }}>
                    <div className="qr-container">
                      <QRCodeSVG 
                        value={mfaSetupData.qr_code_uri} 
                        size={200}
                        style={{ display: 'block', margin: '0 auto', background: 'white', padding: '10px' }}
                      />
                    </div>
                    <p style={{ fontFamily: 'monospace', fontSize: '0.85rem', color: 'var(--text-secondary)', margin: '0.5rem 0 1rem 0' }}>
                      Manual Key: {mfaSetupData.secret}
                    </p>
                  </div>
                )}

                <h3 style={{ fontSize: '1.1rem', marginBottom: '0.5rem', marginTop: '1rem', fontWeight: 500 }}>2. Save Backup Codes</h3>
                <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
                  Store these in a secure place. Each code can only be used once:
                </p>
                <div className="backup-grid">
                  {mfaSetupData.backup_codes?.map((code: string, i: number) => (
                    <div key={i} className="backup-code">{code}</div>
                  ))}
                </div>

                <form onSubmit={handleConfirm2fa} style={{ marginTop: '1.5rem' }}>
                  <h3 style={{ fontSize: '1.1rem', marginBottom: '0.75rem', fontWeight: 500 }}>3. Verify Activation</h3>
                  <div className="form-group">
                    <label htmlFor="totpVerificationCode" className="form-label">App Verification Code</label>
                    <input
                      id="totpVerificationCode"
                      type="text"
                      className="form-input"
                      placeholder="000000"
                      value={totpVerificationCode}
                      onChange={(e) => setTotpVerificationCode(e.target.value)}
                      maxLength={6}
                      required
                    />
                  </div>
                  <div className="flex gap-md" style={{ marginTop: '1rem' }}>
                    <button type="submit" className="btn btn-success" style={{ flexGrow: 1 }}>
                      Activate 2FA
                    </button>
                    <button
                      type="button"
                      className="btn btn-secondary"
                      onClick={() => setMfaSetupData(null)}
                    >
                      Cancel
                    </button>
                  </div>
                </form>
              </div>
            )}

            {/* If 2FA is enabled */}
            {isMfaEnabled && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', marginTop: '1rem' }}>
                {!disablingMfa ? (
                  <>
                    <button
                      onClick={handleRegenerateBackupCodes}
                      className="btn btn-secondary"
                      style={{ width: '100%' }}
                    >
                      <RefreshCw size={16} /> Regenerate Backup Codes
                    </button>
                    <button
                      onClick={() => setDisablingMfa(true)}
                      className="btn btn-danger"
                      style={{ width: '100%' }}
                    >
                      Disable 2FA
                    </button>
                  </>
                ) : (
                  <form onSubmit={handleDisable2fa} style={{ borderTop: '1px solid var(--border-glass)', paddingTop: '1rem', marginTop: '1rem' }}>
                    <div className="form-group">
                      <label htmlFor="disableMethod" className="form-label">Verification Method</label>
                      <select 
                        id="disableMethod"
                        className="form-input" 
                        value={disableMethod} 
                        onChange={(e) => setDisableMethod(e.target.value as 'password' | 'totp')}
                        style={{ marginBottom: '1rem' }}
                      >
                        <option value="totp">TOTP App Code</option>
                        <option value="password">Account Password</option>
                      </select>
                    </div>
                    <div className="form-group">
                      <label htmlFor="disableCredential" className="form-label">{disableMethod === 'totp' ? 'TOTP Code' : 'Account Password'}</label>
                      <input
                        id="disableCredential"
                        type={disableMethod === 'totp' ? 'text' : 'password'}
                        className="form-input"
                        placeholder={disableMethod === 'totp' ? '6-digit code' : 'Password'}
                        value={disableCredential}
                        onChange={(e) => setDisableCredential(e.target.value)}
                        required
                      />
                    </div>
                    <div className="flex gap-md" style={{ marginTop: '1rem' }}>
                      <button type="submit" className="btn btn-danger" style={{ flexGrow: 1 }}>
                        Confirm Disable
                      </button>
                      <button
                        type="button"
                        className="btn btn-secondary"
                        onClick={() => {
                          setDisablingMfa(false);
                          setDisableCredential('');
                        }}
                      >
                        Cancel
                      </button>
                    </div>
                  </form>
                )}

                {/* Show newly generated backup codes after refresh */}
                {mfaSetupData && mfaSetupData.qr_code_uri === null && (
                  <div style={{ marginTop: '1.5rem', background: 'rgba(255, 255, 255, 0.05)', padding: '1rem', border: '1px solid var(--border-glass)' }}>
                    <p style={{ fontWeight: 500, color: 'var(--text-primary)', fontSize: '0.9rem', marginBottom: '0.5rem' }}>
                      Newly Generated Backup Codes:
                    </p>
                    <div className="backup-grid">
                      {mfaSetupData.backup_codes?.map((code: string, i: number) => (
                        <div key={i} className="backup-code">{code}</div>
                      ))}
                    </div>
                    <button className="btn btn-secondary" style={{ width: '100%', fontSize: '0.8rem', padding: '0.6rem' }} onClick={() => setMfaSetupData(null)}>
                      I have saved them
                    </button>
                  </div>
                )}
              </div>
            )}
          </motion.div>

          {/* Passkeys Card */}
          <motion.div className="glass-card" whileHover={{ scale: 1.01 }}>
            <h2 style={{ fontSize: '1.25rem', marginBottom: '1.25rem', display: 'flex', alignItems: 'center', gap: '0.5rem', fontWeight: 500 }}>
              <Key size={20} /> Passkeys (Biometrics)
            </h2>
            <div style={{ marginBottom: '1.5rem' }}>
              <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
                Sign in securely with Fingerprint, Face ID, or Windows Hello without typing a password.
              </p>
            </div>
            <button 
              onClick={handleRegisterPasskey} 
              className="btn btn-primary" 
              style={{ width: '100%' }} 
              disabled={actionLoading === 'registerPasskey'}
            >
              {actionLoading === 'registerPasskey' ? 'Loading...' : 'Add Passkey'}
            </button>
          </motion.div>
        </div>

        {/* Right Column: Sessions and Linked Accounts */}
        <div className="flex flex-col gap-lg">
          
          {/* Linked OAuth Accounts */}
          <motion.div className="glass-card" whileHover={{ scale: 1.01 }}>
            <h2 style={{ fontSize: '1.25rem', marginBottom: '1.25rem', display: 'flex', alignItems: 'center', gap: '0.5rem', fontWeight: 500 }}>
              <Link2 size={20} /> Linked Social Accounts
            </h2>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              {allProviders.map((provider) => {
                const linked = linkedAccounts.find((acc) => acc.provider === provider);
                return (
                  <div
                    key={provider}
                    className="flex align-center justify-between"
                    style={{
                      padding: '1rem',
                      background: 'transparent',
                      border: '1px solid var(--border-glass)',
                    }}
                  >
                    <div>
                      <span style={{ fontWeight: 500, textTransform: 'capitalize' }}>{provider}</span>
                      {linked ? (
                        <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                          Linked: {linked.provider_email || 'Yes'}
                        </p>
                      ) : (
                        <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Not linked</p>
                      )}
                    </div>
                    {linked ? (
                      <button
                        onClick={() => handleUnlinkAccount(provider)}
                        className="btn btn-secondary"
                        style={{ padding: '0.4rem 0.8rem', fontSize: '0.8rem' }}
                        disabled={actionLoading === `unlink-${provider}`}
                      >
                        <Unlink size={14} /> {actionLoading === `unlink-${provider}` ? 'Unlinking...' : 'Unlink'}
                      </button>
                    ) : (
                      <button
                        onClick={() => handleLinkAccount(provider)}
                        className="btn btn-secondary"
                        style={{ padding: '0.4rem 0.8rem', fontSize: '0.8rem' }}
                      >
                        <Link2 size={14} /> Link
                      </button>
                    )}
                  </div>
                );
              })}
            </div>
          </motion.div>

          {/* Active Sessions */}
          <motion.div className="glass-card" whileHover={{ scale: 1.01 }}>
            <div className="flex justify-between align-center" style={{ marginBottom: '1.25rem' }}>
              <h2 style={{ fontSize: '1.25rem', display: 'flex', alignItems: 'center', gap: '0.5rem', fontWeight: 500 }}>
                <Layers size={20} /> Active Sessions
              </h2>
              {sessions.length > 1 && (
                <button
                  onClick={handleLogoutAllOther}
                  className="btn btn-danger"
                  style={{ padding: '0.4rem 0.8rem', fontSize: '0.8rem' }}
                  disabled={actionLoading === 'logoutAll'}
                >
                  <Trash2 size={14} /> {actionLoading === 'logoutAll' ? 'Logging out...' : 'Sign out other devices'}
                </button>
              )}
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              {sessions.map((sess) => {
                let DeviceIcon = Monitor;
                if (sess.device_type === 'Mobile') DeviceIcon = Smartphone;
                else if (sess.device_type === 'Tablet') DeviceIcon = Smartphone;
                else if (sess.device_type === 'PC') DeviceIcon = Laptop;
                else if (sess.device_type === 'Bot') DeviceIcon = Server;

                return (
                  <div
                    key={sess.id}
                    style={{
                      padding: '1rem',
                      background: 'rgba(255, 255, 255, 0.02)',
                      border: '1px solid var(--border-glass)',
                      borderRadius: '8px',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '0.75rem'
                    }}
                  >
                    <div className="flex justify-between align-center">
                      <div className="flex align-center gap-sm">
                        <DeviceIcon size={18} style={{ color: 'var(--primary-color)' }} />
                        <span style={{ fontWeight: 600, fontSize: '0.95rem' }}>
                          {sess.os_info || 'Unknown Device'}
                        </span>
                      </div>
                      <span className="badge badge-purple" style={{ fontSize: '0.65rem' }}>
                        {sess.id.substring(0, 8)}...
                      </span>
                    </div>

                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem', paddingLeft: '24px' }}>
                      <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                        <span style={{ fontWeight: 500 }}>{sess.browser_info || sess.user_agent || 'Unknown Browser'}</span>
                      </p>
                      <div style={{ display: 'flex', gap: '1rem', marginTop: '0.25rem' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.25rem', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                          <Activity size={12} /> {sess.ip_address}
                        </div>
                        {sess.location && (
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.25rem', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                            <MapPin size={12} /> {sess.location}
                          </div>
                        )}
                      </div>
                      <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
                        Active since: {new Date(sess.created_at).toLocaleString()}
                      </p>
                    </div>

                    <button
                      onClick={() => handleRevokeSession(sess.id)}
                      className="btn btn-secondary"
                      style={{ padding: '0.4rem 0.8rem', fontSize: '0.8rem', marginTop: '0.25rem', width: '100%', borderColor: 'rgba(239, 68, 68, 0.3)', color: 'var(--text-primary)', transition: 'all 0.2s' }}
                      disabled={actionLoading === `revoke-${sess.id}`}
                    >
                      <Trash2 size={14} style={{ display: 'inline', marginRight: '6px', color: 'var(--danger-color)' }} /> 
                      {actionLoading === `revoke-${sess.id}` ? 'Revoking...' : 'Revoke Session'}
                    </button>
                  </div>
                );
              })}
            </div>
          </motion.div>

          {/* Security Audit History */}
          <motion.div className="glass-card" whileHover={{ scale: 1.01 }}>
            <h2 style={{ fontSize: '1.25rem', marginBottom: '1.25rem', display: 'flex', alignItems: 'center', gap: '0.5rem', fontWeight: 500 }}>
              <History size={20} /> Security History
            </h2>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', maxHeight: '400px', overflowY: 'auto', paddingRight: '0.5rem' }}>
              {auditLogs.length === 0 ? (
                <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>No recent activity.</p>
              ) : (
                auditLogs.map((log) => {
                  let badgeClass = 'badge badge-gray';
                  if (log.action.includes('success') || log.action === 'email_verified' || log.action.includes('enabled')) {
                    badgeClass = 'badge badge-green';
                  } else if (log.action.includes('failed') || log.action.includes('suspicious') || log.action.includes('attack')) {
                    badgeClass = 'badge badge-red';
                  } else if (log.action.includes('revoked') || log.action.includes('logged_out') || log.action.includes('disabled')) {
                    badgeClass = 'badge badge-purple';
                  }

                  return (
                    <div
                      key={log.id}
                      style={{
                        padding: '1rem',
                        background: 'transparent',
                        border: '1px solid var(--border-glass)',
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '0.5rem'
                      }}
                    >
                      <div className="flex justify-between align-center">
                        <span className={badgeClass} style={{ fontSize: '0.7rem', fontWeight: 600 }}>
                          {log.action.replace(/_/g, ' ').toUpperCase()}
                        </span>
                        <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                          {new Date(log.timestamp).toLocaleString()}
                        </span>
                      </div>
                      
                      <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                          <Activity size={12} /> {log.ip_address || 'Unknown IP'}
                        </div>
                        {log.user_agent && (
                          <div style={{ marginTop: '0.25rem', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                            {log.user_agent}
                          </div>
                        )}
                        {log.metadata && Object.keys(log.metadata).length > 0 && (
                          <div style={{ marginTop: '0.5rem', padding: '0.5rem', background: 'rgba(0,0,0,0.2)', borderRadius: '4px', fontFamily: 'monospace', fontSize: '0.7rem' }}>
                            {JSON.stringify(log.metadata)}
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </motion.div>

        </div>
      </div>
    </div>
  );
};
