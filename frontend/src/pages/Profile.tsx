import React, { useState, useEffect } from 'react';
import { Shield, Smartphone, Trash2, Link2, Unlink, CheckCircle, AlertCircle, RefreshCw, Layers, Key } from 'lucide-react';
import { api, API_BASE_URL } from '../services/api';
import { QRCodeSVG } from 'qrcode.react';
import { motion } from 'framer-motion';

export const Profile: React.FC = () => {
  const [user, setUser] = useState<any>(null);
  const [sessions, setSessions] = useState<any[]>([]);
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
    } catch (err: any) {
      setError(err.message || 'Ошибка загрузки данных профиля');
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
      setError(err.message || 'Ошибка выхода из других сессий');
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
      setSuccess(`Аккаунт ${provider} успешно отвязан.`);
      await fetchData();
    } catch (err: any) {
      setError(err.message || 'Ошибка отвязки аккаунта');
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
      setError(err.message || 'Ошибка инициализации 2FA');
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
      setSuccess('Двухфакторная аутентификация (2FA) успешно включена.');
      setMfaSetupData(null);
      setTotpVerificationCode('');
      fetchData();
    } catch (err: any) {
      setError(err.message || 'Неверный проверочный код TOTP');
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
      setSuccess('2FA успешно отключена!');
      setMfaSetupData(null);
      setTotpVerificationCode('');
      await fetchData();
    } catch (err: any) {
      setError(err.message || 'Ошибка отключения 2FA');
    }
  };

  const handleRegenerateBackupCodes = async () => {
    setError('');
    setSuccess('');
    try {
      const resp = await api.post('/api/v1/auth/2fa/backup-codes/regenerate');
      setMfaSetupData({
        backup_codes: resp.data.backup_codes,
        secret: 'Запрос на перегенерацию',
        qr_code_uri: null,
      });
      setSuccess('Новые резервные коды сгенерированы. Пожалуйста, сохраните их!');
    } catch (err: any) {
      setError(err.message || 'Ошибка регенерации резервных кодов');
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
        throw new Error('Регистрация биометрии отменена или не удалась');
      }

      // 3. Complete
      const deviceName = window.prompt("Введите имя устройства для Passkey:", "Мое устройство");
      await api.post('/api/v1/auth/webauthn/register/complete', {
        response: asseResp,
        name: deviceName || 'New Passkey'
      });

      setSuccess('Passkey успешно добавлен!');
      await fetchData();
    } catch (err: any) {
      setError(err.message || 'Ошибка регистрации Passkey');
    } finally {
      setActionLoading(null);
    }
  };

  if (loading) {
    return <div className="flex-center" style={{ minHeight: '50vh' }}>Загрузка профиля...</div>;
  }

  const isMfaEnabled = user?.two_factor_enabled || false;
  const allProviders = ['google', 'github', 'discord', 'apple', 'facebook', 'twitter', 'amazon'];

  return (
    <div>
      {/* Page Header */}
      <div className="page-header">
        <h1 className="page-title">Личный кабинет</h1>
        <p className="page-subtitle">Управляйте безопасностью аккаунта, активными сессиями и подключенными соцсетями</p>
      </div>

      {/* Alert Banners */}
      {error && (
        <div className="alert alert-error">
          <AlertCircle size={20} />
          <span>{error}</span>
        </div>
      )}
      {success && (
        <div className="alert alert-success">
          <CheckCircle size={20} />
          <span>{success}</span>
        </div>
      )}

      <div className="grid-2">
        {/* Left Column: Security Settings */}
        <div className="flex flex-col gap-lg">
          
          {/* User Info Card */}
          <motion.div className="glass-card glass" whileHover={{ scale: 1.02 }}>
            <h2 style={{ fontSize: '1.25rem', marginBottom: '1.25rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Smartphone size={20} /> Информация об аккаунте
            </h2>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              <div>
                <span style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>Email</span>
                <p style={{ fontWeight: 500, fontSize: '1.1rem' }}>{user?.email}</p>
              </div>
              <div>
                <span style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>Роль</span>
                <p style={{ fontWeight: 500 }}><span className="badge badge-purple">{user?.role}</span></p>
              </div>
              <div>
                <span style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>Статус</span>
                <p style={{ fontWeight: 500 }}>
                  <span className={user?.is_active ? 'badge badge-green' : 'badge badge-red'}>
                    {user?.is_active ? 'Активен' : 'Отключен'}
                  </span>
                </p>
              </div>
            </div>
          </motion.div>

          {/* 2FA Card */}
          <motion.div className="glass-card glass" whileHover={{ scale: 1.02 }}>
            <h2 style={{ fontSize: '1.25rem', marginBottom: '1.25rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Shield size={20} /> Двухфакторная аутентификация (2FA)
            </h2>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.5rem' }}>
              <div>
                <p style={{ fontWeight: 600 }}>Двухфакторный вход</p>
                <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
                  {isMfaEnabled 
                    ? 'Ваш аккаунт надежно защищен дополнительным кодом.' 
                    : 'Дополнительный уровень безопасности для вашего аккаунта.'}
                </p>
              </div>
              <span className={isMfaEnabled ? 'badge badge-green' : 'badge badge-red'}>
                {isMfaEnabled ? 'Включено' : 'Выключено'}
              </span>
            </div>

            {/* If 2FA is not enabled and setup is not in progress */}
            {!isMfaEnabled && !mfaSetupData && (
              <button onClick={handleStart2faSetup} className="btn btn-primary" style={{ width: '100%' }} disabled={actionLoading === 'start2fa'}>
                {actionLoading === 'start2fa' ? 'Загрузка...' : 'Настроить 2FA (TOTP)'}
              </button>
            )}

            {/* If 2FA Setup is in progress */}
            {mfaSetupData && !isMfaEnabled && (
              <div style={{ marginTop: '1.5rem', borderTop: '1px solid var(--border-glass)', paddingTop: '1.5rem' }}>
                <h3 style={{ fontSize: '1.1rem', marginBottom: '0.5rem' }}>1. Отсканируйте QR-код</h3>
                <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', marginBottom: '1rem' }}>
                  Используйте Google Authenticator, Yandex Key или другое приложение для сканирования:
                </p>
                {mfaSetupData.qr_code_uri && (
                  <div style={{ textAlign: 'center' }}>
                    <div className="qr-container">
                      <QRCodeSVG 
                        value={mfaSetupData.qr_code_uri} 
                        size={200}
                        style={{ display: 'block', margin: '0 auto', background: 'white', padding: '10px', borderRadius: '8px' }}
                      />
                    </div>
                    <p style={{ fontFamily: 'monospace', fontSize: '0.85rem', color: 'var(--text-secondary)', margin: '0.5rem 0 1rem 0' }}>
                      Ключ вручную: {mfaSetupData.secret}
                    </p>
                  </div>
                )}

                <h3 style={{ fontSize: '1.1rem', marginBottom: '0.5rem', marginTop: '1rem' }}>2. Сохраните резервные коды</h3>
                <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
                  Сохраните эти коды в безопасном месте. Каждый код может быть использован только один раз для входа при утере телефона:
                </p>
                <div className="backup-grid">
                  {mfaSetupData.backup_codes?.map((code: string, i: number) => (
                    <div key={i} className="backup-code">{code}</div>
                  ))}
                </div>

                <form onSubmit={handleConfirm2fa} style={{ marginTop: '1.5rem' }}>
                  <h3 style={{ fontSize: '1.1rem', marginBottom: '0.75rem' }}>3. Подтвердите активацию</h3>
                  <div className="form-group">
                    <label className="form-label">Проверочный код из приложения</label>
                    <input
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
                      Активировать 2FA
                    </button>
                    <button
                      type="button"
                      className="btn btn-secondary"
                      onClick={() => setMfaSetupData(null)}
                    >
                      Отмена
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
                      <RefreshCw size={16} /> Перегенерировать резервные коды
                    </button>
                    <button
                      onClick={() => setDisablingMfa(true)}
                      className="btn btn-danger"
                      style={{ width: '100%' }}
                    >
                      Отключить 2FA
                    </button>
                  </>
                ) : (
                  <form onSubmit={handleDisable2fa} style={{ borderTop: '1px solid var(--border-glass)', paddingTop: '1rem', marginTop: '1rem' }}>
                    <div className="form-group">
                      <label className="form-label">Способ подтверждения</label>
                      <select 
                        className="form-input" 
                        value={disableMethod} 
                        onChange={(e) => setDisableMethod(e.target.value as 'password' | 'totp')}
                        style={{ marginBottom: '1rem' }}
                      >
                        <option value="totp">Код TOTP</option>
                        <option value="password">Пароль</option>
                      </select>
                    </div>
                    <div className="form-group">
                      <label className="form-label">{disableMethod === 'totp' ? 'Код TOTP' : 'Пароль аккаунта'}</label>
                      <input
                        type={disableMethod === 'totp' ? 'text' : 'password'}
                        className="form-input"
                        placeholder={disableMethod === 'totp' ? 'Код 2FA' : 'Пароль'}
                        value={disableCredential}
                        onChange={(e) => setDisableCredential(e.target.value)}
                        required
                      />
                    </div>
                    <div className="flex gap-md" style={{ marginTop: '1rem' }}>
                      <button type="submit" className="btn btn-danger" style={{ flexGrow: 1 }}>
                        Подтвердить отключение
                      </button>
                      <button
                        type="button"
                        className="btn btn-secondary"
                        onClick={() => {
                          setDisablingMfa(false);
                          setDisableCredential('');
                        }}
                      >
                        Отмена
                      </button>
                    </div>
                  </form>
                )}

                {/* Show newly generated backup codes after refresh */}
                {mfaSetupData && mfaSetupData.qr_code_uri === null && (
                  <div style={{ marginTop: '1.5rem', background: 'rgba(245, 158, 11, 0.05)', padding: '1rem', borderRadius: 'var(--border-radius-md)', border: '1px solid rgba(245, 158, 11, 0.2)' }}>
                    <p style={{ fontWeight: 600, color: 'var(--color-warning)', fontSize: '0.9rem', marginBottom: '0.5rem' }}>
                      Новые сгенерированные резервные коды:
                    </p>
                    <div className="backup-grid">
                      {mfaSetupData.backup_codes?.map((code: string, i: number) => (
                        <div key={i} className="backup-code">{code}</div>
                      ))}
                    </div>
                    <button className="btn btn-secondary" style={{ width: '100%', fontSize: '0.8rem', padding: '0.4rem' }} onClick={() => setMfaSetupData(null)}>
                      Я их сохранил
                    </button>
                  </div>
                )}
              </div>
            )}
          </motion.div>

          {/* Passkeys Card */}
          <motion.div className="glass-card glass" whileHover={{ scale: 1.02 }}>
            <h2 style={{ fontSize: '1.25rem', marginBottom: '1.25rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Key size={20} /> Passkeys (Биометрия)
            </h2>
            <div style={{ marginBottom: '1.5rem' }}>
              <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
                Входите в аккаунт с помощью отпечатка пальца, Face ID или Windows Hello без пароля.
              </p>
            </div>
            <button 
              onClick={handleRegisterPasskey} 
              className="btn btn-primary" 
              style={{ width: '100%' }} 
              disabled={actionLoading === 'registerPasskey'}
            >
              {actionLoading === 'registerPasskey' ? 'Загрузка...' : 'Добавить Passkey'}
            </button>
          </motion.div>
        </div>

        {/* Right Column: Sessions and Linked Accounts */}
        <div className="flex flex-col gap-lg">
          
          {/* Linked OAuth Accounts */}
          <motion.div className="glass-card glass" whileHover={{ scale: 1.02 }}>
            <h2 style={{ fontSize: '1.25rem', marginBottom: '1.25rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Link2 size={20} /> Подключенные соцсети
            </h2>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              {allProviders.map((provider) => {
                const linked = linkedAccounts.find((acc) => acc.provider === provider);
                return (
                  <div
                    key={provider}
                    className="flex align-center justify-between"
                    style={{
                      padding: '0.75rem 1rem',
                      background: 'rgba(255,255,255,0.02)',
                      border: '1px solid var(--border-glass)',
                      borderRadius: 'var(--border-radius-md)',
                    }}
                  >
                    <div>
                      <span style={{ fontWeight: 600, textTransform: 'capitalize' }}>{provider}</span>
                      {linked ? (
                        <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                          Связано: {linked.provider_email || 'Да'}
                        </p>
                      ) : (
                        <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Не привязано</p>
                      )}
                    </div>
                    {linked ? (
                      <button
                        onClick={() => handleUnlinkAccount(provider)}
                        className="btn btn-secondary"
                        style={{ padding: '0.4rem 0.8rem', fontSize: '0.8rem' }}
                        disabled={actionLoading === `unlink-${provider}`}
                      >
                        <Unlink size={14} /> {actionLoading === `unlink-${provider}` ? 'Отвязка...' : 'Отвязать'}
                      </button>
                    ) : (
                      <button
                        onClick={() => handleLinkAccount(provider)}
                        className="btn btn-primary"
                        style={{ padding: '0.4rem 0.8rem', fontSize: '0.8rem' }}
                      >
                        <Link2 size={14} /> Привязать
                      </button>
                    )}
                  </div>
                );
              })}
            </div>
          </motion.div>

          {/* Active Sessions */}
          <motion.div className="glass-card glass" whileHover={{ scale: 1.02 }}>
            <div className="flex justify-between align-center" style={{ marginBottom: '1.25rem' }}>
              <h2 style={{ fontSize: '1.25rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <Layers size={20} /> Активные сеансы
              </h2>
              {sessions.length > 1 && (
                <button
                  onClick={handleLogoutAllOther}
                  className="btn btn-danger"
                  style={{ padding: '0.4rem 0.8rem', fontSize: '0.8rem' }}
                  disabled={actionLoading === 'logoutAll'}
                >
                  <Trash2 size={14} /> {actionLoading === 'logoutAll' ? 'Выход...' : 'Выйти на других устройствах'}
                </button>
              )}
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              {sessions.map((sess) => (
                <div
                  key={sess.id}
                  style={{
                    padding: '1rem',
                    background: 'rgba(255,255,255,0.02)',
                    border: '1px solid var(--border-glass)',
                    borderRadius: 'var(--border-radius-md)',
                  }}
                >
                  <div className="flex justify-between align-center" style={{ marginBottom: '0.25rem' }}>
                    <span style={{ fontWeight: 600, fontSize: '0.95rem' }}>
                      {sess.ip_address}
                    </span>
                    <span className="badge badge-purple" style={{ fontSize: '0.65rem' }}>
                      {sess.id.substring(0, 8)}...
                    </span>
                  </div>
                  <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    Устройство: {sess.user_agent}
                  </p>
                  <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
                    Создан: {new Date(sess.created_at).toLocaleString()}
                  </p>
                </div>
              ))}
            </div>
          </motion.div>

        </div>
      </div>
    </div>
  );
};
