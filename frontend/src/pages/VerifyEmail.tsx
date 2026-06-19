import React, { useEffect, useState } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { CheckCircle, XCircle, Loader2 } from 'lucide-react';
import { api } from '../services/api';

export const VerifyEmail: React.FC = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading');
  const [message, setMessage] = useState('');

  useEffect(() => {
    const token = searchParams.get('token');
    if (!token) {
      setStatus('error');
      setMessage('Токен не найден в URL');
      return;
    }

    const verify = async () => {
      try {
        await api.get(`/api/v1/auth/verify-email?token=${token}`);
        setStatus('success');
        setMessage('Почта подтверждена');
      } catch (err: any) {
        setStatus('error');
        setMessage(err.message || 'Ошибка подтверждения');
      }
    };

    verify();
  }, [searchParams]);

  return (
    <div className="auth-page">
      <div className="glass-card auth-card glow-card" style={{ textAlign: 'center', padding: '3rem 2rem' }}>
        {status === 'loading' && (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
            <Loader2 
              size={48} 
              style={{ 
                color: 'var(--primary-color, #3b82f6)',
                animation: 'spin 1s linear infinite'
              }} 
            />
            <h2 style={{ marginTop: '1.5rem', fontSize: '1.5rem' }}>Проверка...</h2>
            <style>{`
              @keyframes spin {
                from { transform: rotate(0deg); }
                to { transform: rotate(360deg); }
              }
            `}</style>
          </div>
        )}
        
        {status === 'success' && (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
            <CheckCircle size={48} style={{ color: 'var(--success-color, #10b981)' }} />
            <h2 style={{ marginTop: '1.5rem', fontSize: '1.5rem' }}>Успешно</h2>
            <p style={{ marginTop: '0.5rem', color: 'var(--text-secondary, #9ca3af)' }}>{message}</p>
            <button 
              className="btn btn-primary" 
              style={{ marginTop: '2rem', width: '100%' }}
              onClick={() => navigate('/login')}
            >
              Войти
            </button>
          </div>
        )}

        {status === 'error' && (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
            <XCircle size={48} style={{ color: 'var(--error-color, #ef4444)' }} />
            <h2 style={{ marginTop: '1.5rem', fontSize: '1.5rem' }}>Ошибка</h2>
            <p style={{ marginTop: '0.5rem', color: 'var(--text-secondary, #9ca3af)' }}>{message}</p>
            <button 
              className="btn btn-secondary" 
              style={{ marginTop: '2rem', width: '100%' }}
              onClick={() => navigate('/login')}
            >
              На страницу входа
            </button>
          </div>
        )}
      </div>
    </div>
  );
};
