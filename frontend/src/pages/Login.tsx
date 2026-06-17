import React, { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { LogIn, UserPlus, Settings, CheckCircle, AlertCircle, ShieldAlert, Key } from 'lucide-react';
import { api, getApiKey, setApiKey } from '../services/api';

interface LoginProps {
  onLoginSuccess: (user: any) => void;
}

export const Login: React.FC<LoginProps> = ({ onLoginSuccess }) => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  // Auth Forms state
  const [isRegister, setIsRegister] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  
  // Developer/Tenant Settings state
  const [apiKey, setApiKeyInput] = useState(getApiKey());
  const [showSettings, setShowSettings] = useState(false);

  // Status/Error state
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [info, setInfo] = useState('');

  // 2FA Challenge state
  const [requires2fa, setRequires2fa] = useState(false);
  const [mfaToken, setMfaToken] = useState('');
  const [totpCode, setTotpCode] = useState('');

  // OAuth query param handling (when redirecting back from OAuth callback with 2FA required)
  useEffect(() => {
    const oauthRequires2fa = searchParams.get('requires_2fa');
    const oauthMfaToken = searchParams.get('mfa_token');
    
    if (oauthRequires2fa === 'true' && oauthMfaToken) {
      setRequires2fa(true);
      setMfaToken(oauthMfaToken);
      setInfo('Для завершения входа через OAuth требуется двухфакторная аутентификация.');
    }
  }, [searchParams]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setInfo('');
    setLoading(true);

    try {
      if (isRegister) {
        // Registration flow
        await api.post('/api/v1/auth/register', { email, password });
        setInfo('Регистрация прошла успешно! Теперь вы можете войти.');
        setIsRegister(false);
        setPassword('');
      } else {
        // Login flow
        const resp = await api.post('/api/v1/auth/login', { email, password });
        
        if (resp.data.requires_2fa) {
          setRequires2fa(true);
          setMfaToken(resp.data.mfa_token);
          setInfo('Введите код подтверждения 2FA из вашего приложения или резервный код.');
        } else {
          // Successfully logged in
          const meResp = await api.get('/api/v1/auth/me');
          onLoginSuccess(meResp.data);
          navigate('/profile');
        }
      }
    } catch (err: any) {
      setError(err.message || 'Произошла непредвиденная ошибка');
    } finally {
      setLoading(false);
    }
  };

  const handle2faVerify = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const resp = await api.post('/api/v1/auth/2fa/verify', {
        mfa_token: mfaToken,
        totp_code: totpCode,
      });

      // Verification successful, fetch user details
      const meResp = await api.get('/api/v1/auth/me');
      onLoginSuccess(meResp.data);
      navigate('/profile');
    } catch (err: any) {
      setError(err.message || 'Неверный код 2FA');
    } finally {
      setLoading(false);
    }
  };

  const handleOAuthLogin = (provider: string) => {
    // Dynamic client state (where to return after successful login)
    const clientState = window.location.origin + '/profile';
    const loginUrl = `http://localhost:8000/api/v1/auth/oauth/${provider}?state=${encodeURIComponent(clientState)}`;
    window.location.href = loginUrl;
  };

  const saveSettings = (e: React.FormEvent) => {
    e.preventDefault();
    setApiKey(apiKey);
    setShowSettings(false);
    setInfo('Настройки API-ключа тенанта сохранены.');
  };

  return (
    <div className="auth-page">
      <div className="glass-card auth-card glow-card">
        {/* Header */}
        <div style={{ position: 'relative', textAlign: 'center', marginBottom: '2rem' }}>
          <button
            onClick={() => setShowSettings(!showSettings)}
            style={{
              position: 'absolute',
              top: 0,
              right: 0,
              background: 'none',
              border: 'none',
              color: 'var(--text-secondary)',
              cursor: 'pointer',
            }}
          >
            <Settings size={20} />
          </button>
          
          <div className="logo-icon" style={{ margin: '0 auto 1rem auto' }}>AG</div>
          <h2 style={{ fontSize: '1.75rem', fontWeight: 700 }}>
            {requires2fa ? 'Подтверждение 2FA' : isRegister ? 'Регистрация' : 'Вход в систему'}
          </h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginTop: '0.25rem' }}>
            {requires2fa 
              ? 'Защита вашего аккаунта' 
              : isRegister 
                ? 'Создайте учетную запись' 
                : 'Войдите под своей учетной записью'}
          </p>
        </div>

        {/* Status Messages */}
        {error && (
          <div className="alert alert-error">
            <AlertCircle size={20} style={{ flexShrink: 0 }} />
            <span>{error}</span>
          </div>
        )}
        {info && (
          <div className="alert alert-info">
            <CheckCircle size={20} style={{ flexShrink: 0 }} />
            <span>{info}</span>
          </div>
        )}

        {/* Tenant Settings Panel */}
        {showSettings && (
          <form onSubmit={saveSettings} style={{ marginBottom: '1.5rem', padding: '1rem', background: 'rgba(255,255,255,0.02)', borderRadius: 'var(--border-radius-md)', border: '1px solid var(--border-glass)' }}>
            <h3 style={{ fontSize: '1rem', marginBottom: '0.75rem', display: 'flex', alignCenter: 'center', gap: '0.5rem' }}>
              <Key size={16} /> Настройки разработчика (Multi-tenant)
            </h3>
            <div className="form-group">
              <label className="form-label">X-Api-Key тенанта</label>
              <input
                type="text"
                className="form-input"
                value={apiKey}
                onChange={(e) => setApiKeyInput(e.target.value)}
                required
              />
            </div>
            <button type="submit" className="btn btn-secondary" style={{ width: '100%' }}>
              Сохранить настройки
            </button>
          </form>
        )}

        {/* 2FA Challenge Form */}
        {requires2fa ? (
          <form onSubmit={handle2faVerify}>
            <div className="form-group">
              <label className="form-label">Код подтверждения (TOTP / Резервный код)</label>
              <input
                type="text"
                className="form-input"
                placeholder="000000"
                value={totpCode}
                onChange={(e) => setTotpCode(e.target.value)}
                maxLength={8}
                required
                autoFocus
              />
            </div>
            <button type="submit" className="btn btn-primary" style={{ width: '100%', marginTop: '0.5rem' }} disabled={loading}>
              <LogIn size={18} /> {loading ? 'Проверка...' : 'Подтвердить'}
            </button>
            <button
              type="button"
              className="btn btn-secondary"
              style={{ width: '100%', marginTop: '0.75rem' }}
              onClick={() => {
                setRequires2fa(false);
                setMfaToken('');
                setTotpCode('');
                setError('');
                setInfo('');
              }}
            >
              Вернуться назад
            </button>
          </form>
        ) : (
          /* Normal Auth Forms */
          <>
            <form onSubmit={handleSubmit}>
              <div className="form-group">
                <label className="form-label">Электронная почта</label>
                <input
                  type="email"
                  className="form-input"
                  placeholder="name@domain.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                />
              </div>

              <div className="form-group">
                <label className="form-label">Пароль</label>
                <input
                  type="password"
                  className="form-input"
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                />
              </div>

              <button type="submit" className="btn btn-primary" style={{ width: '100%', marginTop: '0.5rem' }} disabled={loading}>
                {isRegister ? <UserPlus size={18} /> : <LogIn size={18} />}
                {loading ? 'Загрузка...' : isRegister ? 'Зарегистрироваться' : 'Войти'}
              </button>
            </form>

            {/* Toggle Sign In / Sign Up */}
            <div style={{ textAlign: 'center', marginTop: '1.5rem', fontSize: '0.9rem', color: 'var(--text-secondary)' }}>
              {isRegister ? (
                <>
                  Уже есть аккаунт?{' '}
                  <button onClick={() => setIsRegister(false)} style={{ background: 'none', border: 'none', color: 'var(--color-primary)', fontWeight: 600, cursor: 'pointer', textDecoration: 'underline' }}>
                    Войдите
                  </button>
                </>
              ) : (
                <>
                  Впервые у нас?{' '}
                  <button onClick={() => setIsRegister(true)} style={{ background: 'none', border: 'none', color: 'var(--color-primary)', fontWeight: 600, cursor: 'pointer', textDecoration: 'underline' }}>
                    Зарегистрируйтесь
                  </button>
                </>
              )}
            </div>

            {/* OAuth Divider */}
            {!isRegister && (
              <>
                <div className="divider">или войти через</div>

                {/* OAuth Buttons */}
                <div className="oauth-grid">
                  <button onClick={() => handleOAuthLogin('google')} className="btn-oauth">
                    Google
                  </button>
                  <button onClick={() => handleOAuthLogin('github')} className="btn-oauth">
                    GitHub
                  </button>
                  <button onClick={() => handleOAuthLogin('discord')} className="btn-oauth">
                    Discord
                  </button>
                  <button onClick={() => handleOAuthLogin('apple')} className="btn-oauth">
                    Apple
                  </button>
                  <button onClick={() => handleOAuthLogin('facebook')} className="btn-oauth">
                    Facebook
                  </button>
                  <button onClick={() => handleOAuthLogin('twitter')} className="btn-oauth">
                    Twitter (X)
                  </button>
                </div>
                
                <button
                  onClick={() => handleOAuthLogin('amazon')}
                  className="btn-oauth"
                  style={{ width: '100%', justifyContent: 'center' }}
                >
                  Войти через Amazon
                </button>
              </>
            )}
          </>
        )}
      </div>
    </div>
  );
};
