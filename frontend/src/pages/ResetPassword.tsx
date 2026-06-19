import React, { useState, useEffect } from 'react';
import { useSearchParams, useNavigate, Link } from 'react-router-dom';
import { api } from '../services/api';

export const ResetPassword = () => {
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token');
  const navigate = useNavigate();

  const [newPassword, setNewPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!token) {
      setError('Отсутствует токен сброса пароля.');
    }
  }, [token]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token) {
      setError('Отсутствует токен сброса пароля.');
      return;
    }
    setLoading(true);
    setError('');
    setSuccess(false);

    try {
      await api.post('/api/v1/auth/reset-password', { token, new_password: newPassword });
      setSuccess(true);
      setNewPassword('');
    } catch (err: any) {
      setError(err.response?.data?.detail || err.response?.data?.error || err.message || 'Произошла ошибка при сбросе пароля');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-card glass-card glow-card">
        <div className="page-header" style={{ marginBottom: '1.5rem', textAlign: 'center' }}>
          <h1 className="page-title">Сброс пароля</h1>
          <p className="page-subtitle">Введите новый пароль</p>
        </div>

        {success ? (
          <>
            <div className="alert alert-success">
              <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0 }}>
                <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
                <polyline points="22 4 12 14.01 9 11.01"></polyline>
              </svg>
              <span>Пароль успешно изменён</span>
            </div>
            <button onClick={() => navigate('/login')} className="btn btn-primary" style={{ width: '100%', marginTop: '1rem' }}>
              Перейти ко входу
            </button>
          </>
        ) : (
          <>
            {error && (
              <div className="alert alert-error">
                <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0 }}>
                  <circle cx="12" cy="12" r="10"></circle>
                  <line x1="12" y1="8" x2="12" y2="12"></line>
                  <line x1="12" y1="16" x2="12.01" y2="16"></line>
                </svg>
                <span>{error}</span>
              </div>
            )}

            <form onSubmit={handleSubmit}>
              <div className="form-group">
                <label className="form-label" htmlFor="password">Новый пароль</label>
                <input
                  type="password"
                  id="password"
                  className="form-input"
                  placeholder="Введите пароль"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  required
                  disabled={!token || loading}
                />
              </div>

              <button type="submit" className="btn btn-primary" style={{ width: '100%', marginTop: '1rem' }} disabled={!token || loading}>
                {loading ? 'Сохранение...' : 'Сохранить пароль'}
              </button>
            </form>

            <div className="divider">или</div>
            
            <div style={{ textAlign: 'center' }}>
              <Link to="/login" style={{ color: 'var(--color-primary)', textDecoration: 'none', fontWeight: 500, fontSize: '0.9rem' }}>
                Вернуться ко входу
              </Link>
            </div>
          </>
        )}
      </div>
    </div>
  );
};
