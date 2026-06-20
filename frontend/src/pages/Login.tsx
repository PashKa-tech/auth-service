import React, { useState, useEffect } from 'react';
import { useNavigate, useSearchParams, Link } from 'react-router-dom';
import { LogIn, UserPlus, Settings, CheckCircle, AlertCircle, Key, Mail } from 'lucide-react';
import { api, getApiKey, setApiKey, API_BASE_URL } from '../services/api';
import { motion } from 'framer-motion';
import { CaptchaWidget, CaptchaResult } from '../components/CaptchaWidget';

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
  const [registrationSuccess, setRegistrationSuccess] = useState(false);
  const [captchaResult, setCaptchaResult] = useState<CaptchaResult | null>(null);
  
  // Developer/Tenant Settings state
  const [apiKey, setApiKeyInput] = useState(getApiKey());
  const [showSettings, setShowSettings] = useState(false);

  // Status/Error state
  const [loading, setLoading] = useState(false);
  const [isPasskeyLoading, setIsPasskeyLoading] = useState(false);
  const [isMagicLinkLoading, setIsMagicLinkLoading] = useState(false);
  const [error, setError] = useState('');
  const [info, setInfo] = useState('');

  // 2FA Challenge state
  const [requires2fa, setRequires2fa] = useState(false);
  const [mfaToken, setMfaToken] = useState('');
  const [totpCode, setTotpCode] = useState('');

  // OAuth query param handling
  useEffect(() => {
    const oauthRequires2fa = searchParams.get('requires_2fa');
    const oauthMfaToken = searchParams.get('mfa_token');
    
    if (oauthRequires2fa === 'true' && oauthMfaToken) {
      setRequires2fa(true);
      setMfaToken(oauthMfaToken);
      setInfo('Two-factor authentication is required to complete OAuth login.');
      
      // Prevent token leakage by removing from URL
      window.history.replaceState({}, document.title, window.location.pathname);
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
        await api.post('/api/v1/auth/register', { 
          email, 
          password,
          captcha_token: captchaResult?.token,
          captcha_id: captchaResult?.id
        });
        setRegistrationSuccess(true);
      } else {
        // Login flow
        const resp = await api.post('/api/v1/auth/login', { 
          email, 
          password,
          captcha_token: captchaResult?.token,
          captcha_id: captchaResult?.id
        });
        
        if (resp.data.requires_2fa) {
          setRequires2fa(true);
          setMfaToken(resp.data.mfa_token);
          setInfo('Enter your 2FA confirmation code or a backup code.');
        } else {
          // Successfully logged in
          const meResp = await api.get('/api/v1/auth/me');
          onLoginSuccess(meResp.data);
          navigate('/profile');
        }
      }
    } catch (err: any) {
      setError(err.message || 'An unexpected error occurred');
    } finally {
      setLoading(false);
    }
  };

  const handle2faVerify = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      await api.post('/api/v1/auth/2fa/verify', {
        mfa_token: mfaToken,
        totp_code: totpCode,
      });

      // Verification successful, fetch user details
      const meResp = await api.get('/api/v1/auth/me');
      onLoginSuccess(meResp.data);
      navigate('/profile');
    } catch (err: any) {
      setError(err.message || 'Invalid 2FA code');
    } finally {
      setLoading(false);
    }
  };

  const handleOAuthLogin = (provider: string) => {
    // Dynamic client state (where to return after successful login)
    const clientState = window.location.origin + '/profile';
    const loginUrl = `${API_BASE_URL}/api/v1/auth/oauth/${provider}?state=${encodeURIComponent(clientState)}`;
    window.location.href = loginUrl;
  };

  const handlePasskeyLogin = async () => {
    if (!email) {
      setError('Enter your email to sign in with Passkey');
      return;
    }
    setError('');
    setInfo('');
    setIsPasskeyLoading(true);

    try {
      // 1. Get options
      const beginResp = await api.post('/api/v1/auth/webauthn/login/begin', { email });
      
      // 2. Start auth
      const { startAuthentication } = await import('@simplewebauthn/browser');
      let asseResp;
      try {
        asseResp = await startAuthentication({ optionsJSON: beginResp.data });
      } catch (e: any) {
        throw new Error('Biometric authentication cancelled or failed');
      }

      // 3. Verify
      await api.post('/api/v1/auth/webauthn/login/complete', {
        email,
        response: asseResp
      });

      // 4. Success
      const meResp = await api.get('/api/v1/auth/me');
      onLoginSuccess(meResp.data);
      navigate('/profile');
    } catch (err: any) {
      setError(err.message || 'Passkey login failed');
    } finally {
      setIsPasskeyLoading(false);
    }
  };

  const handleMagicLinkLogin = async () => {
    if (!email) {
      setError('Enter your email to sign in with a Magic Link');
      return;
    }
    setError('');
    setInfo('');
    setIsMagicLinkLoading(true);

    try {
      await api.post('/api/v1/auth/passwordless/start', { email });
      setInfo('A magic link has been sent to your email. Please check your inbox.');
    } catch (err: any) {
      setError(err.message || 'Failed to send magic link');
    } finally {
      setIsMagicLinkLoading(false);
    }
  };

  const saveSettings = (e: React.FormEvent) => {
    e.preventDefault();
    setApiKey(apiKey);
    setShowSettings(false);
    setInfo('Tenant API key settings saved.');
  };

  return (
    <div className="auth-page">
      <motion.div 
        className="glass-card auth-card"
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3, ease: 'easeOut' }}
      >
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
          
          <div className="logo-icon" style={{ margin: '0 auto 1.5rem auto' }}>AG</div>
          <h2 style={{ fontSize: '1.75rem', fontWeight: 600 }}>
            {requires2fa ? '2FA Verification' : isRegister ? 'Create Account' : 'Sign In'}
          </h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginTop: '0.25rem' }}>
            {requires2fa 
              ? 'Protecting your account' 
              : isRegister 
                ? 'Join our platform today' 
                : 'Welcome back to your dashboard'}
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
          <form onSubmit={saveSettings} style={{ marginBottom: '1.5rem', padding: '1.5rem', border: '1px solid var(--border-glass)' }}>
            <h3 style={{ fontSize: '1rem', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem', fontWeight: 500 }}>
              <Key size={16} /> Developer Settings (Multi-tenant)
            </h3>
            <div className="form-group">
              <label className="form-label">Tenant X-Api-Key</label>
              <input
                type="text"
                className="form-input"
                value={apiKey}
                onChange={(e) => setApiKeyInput(e.target.value)}
                required
              />
            </div>
            <button type="submit" className="btn btn-secondary" style={{ width: '100%' }}>
              Save Settings
            </button>
          </form>
        )}

        {/* 2FA Challenge Form */}
        {requires2fa ? (
          <form onSubmit={handle2faVerify}>
            <div className="form-group">
              <label className="form-label">Authentication Code (TOTP / Backup)</label>
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
              <LogIn size={18} /> {loading ? 'Verifying...' : 'Verify'}
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
              Go Back
            </button>
          </form>
        ) : registrationSuccess ? (
          <div className="flex-col flex-center" style={{ textAlign: 'center', padding: '2rem 0' }}>
            <motion.div
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              transition={{ type: 'spring', stiffness: 200, damping: 20 }}
            >
              <CheckCircle size={64} color="var(--text-primary)" style={{ margin: '0 auto 1.5rem auto', display: 'block' }} />
            </motion.div>
            <h3 style={{ fontSize: '1.5rem', marginBottom: '1rem' }}>Success!</h3>
            <p style={{ color: 'var(--text-secondary)', marginBottom: '2rem' }}>
              Please check your email to verify your account.
            </p>
            <button
              onClick={() => {
                setRegistrationSuccess(false);
                setIsRegister(false);
                setPassword('');
                setInfo('');
              }}
              className="btn btn-primary"
              style={{ width: '100%' }}
            >
              Proceed to Sign In
            </button>
          </div>
        ) : (
          /* Normal Auth Forms */
          <>
            <form onSubmit={handleSubmit}>
              <div className="form-group">
                <label className="form-label">Email Address</label>
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
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                  <label className="form-label" style={{ marginBottom: 0 }}>Password</label>
                  {!isRegister && (
                    <Link to="/forgot-password" style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', textDecoration: 'none', fontWeight: 500 }}>
                      Forgot password?
                    </Link>
                  )}
                </div>
                <input
                  type="password"
                  className="form-input"
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                />
              </div>

              <CaptchaWidget onVerify={setCaptchaResult} />

              <button type="submit" className="btn btn-primary" style={{ width: '100%', marginTop: '0.5rem' }} disabled={loading}>
                {isRegister ? <UserPlus size={18} /> : <LogIn size={18} />}
                {loading ? 'Processing...' : isRegister ? 'Create Account' : 'Sign In'}
              </button>

              {!isRegister && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', marginTop: '0.75rem' }}>
                  <button 
                    type="button" 
                    onClick={handlePasskeyLogin} 
                    className="btn btn-secondary" 
                    style={{ width: '100%' }} 
                    disabled={loading || isPasskeyLoading || isMagicLinkLoading}
                  >
                    <Key size={18} /> {isPasskeyLoading ? 'Waiting for device...' : 'Sign in with Passkey'}
                  </button>
                  
                  <button 
                    type="button" 
                    onClick={handleMagicLinkLogin} 
                    className="btn btn-secondary" 
                    style={{ width: '100%' }} 
                    disabled={loading || isPasskeyLoading || isMagicLinkLoading}
                  >
                    <Mail size={18} /> {isMagicLinkLoading ? 'Sending link...' : 'Sign in with Magic Link'}
                  </button>
                </div>
              )}
            </form>

            {/* Toggle Sign In / Sign Up */}
            <div style={{ textAlign: 'center', marginTop: '1.5rem', fontSize: '0.85rem', color: 'var(--text-secondary)', fontWeight: 500 }}>
              {isRegister ? (
                <>
                  Already have an account?{' '}
                  <button onClick={() => setIsRegister(false)} style={{ background: 'none', border: 'none', color: 'var(--text-primary)', fontWeight: 600, cursor: 'pointer', borderBottom: '1px solid var(--text-primary)', paddingBottom: '2px' }}>
                    Sign in
                  </button>
                </>
              ) : (
                <>
                  Don't have an account?{' '}
                  <button onClick={() => setIsRegister(true)} style={{ background: 'none', border: 'none', color: 'var(--text-primary)', fontWeight: 600, cursor: 'pointer', borderBottom: '1px solid var(--text-primary)', paddingBottom: '2px' }}>
                    Sign up
                  </button>
                </>
              )}
            </div>

            {/* OAuth Divider */}
            {!isRegister && (
              <>
                <div className="divider">or continue with</div>

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
                  <button onClick={() => handleOAuthLogin('amazon')} className="btn-oauth">
                    Amazon
                  </button>
                </div>
              </>
            )}
          </>
        )}
      </motion.div>
    </div>
  );
};
