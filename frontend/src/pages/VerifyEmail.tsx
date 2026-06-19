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
      setMessage('Token not found in URL');
      return;
    }

    const verify = async () => {
      try {
        await api.get(`/api/v1/auth/verify-email?token=${token}`);
        setStatus('success');
        setMessage('Email successfully verified');
      } catch (err: any) {
        setStatus('error');
        setMessage(err.message || 'Verification error');
      }
    };

    verify();
  }, [searchParams]);

  return (
    <div className="auth-page">
      <div className="glass-card auth-card" style={{ textAlign: 'center', padding: '3rem 2rem' }}>
        {status === 'loading' && (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
            <Loader2 
              size={48} 
              style={{ 
                color: 'var(--text-primary)',
                animation: 'spin 1s linear infinite'
              }} 
            />
            <h2 style={{ marginTop: '1.5rem', fontSize: '1.5rem', fontWeight: 600 }}>Verifying...</h2>
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
            <CheckCircle size={48} style={{ color: 'var(--text-primary)' }} />
            <h2 style={{ marginTop: '1.5rem', fontSize: '1.5rem', fontWeight: 600 }}>Success</h2>
            <p style={{ marginTop: '0.5rem', color: 'var(--text-secondary)' }}>{message}</p>
            <button 
              className="btn btn-primary" 
              style={{ marginTop: '2rem', width: '100%' }}
              onClick={() => navigate('/login')}
            >
              Sign In
            </button>
          </div>
        )}

        {status === 'error' && (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
            <XCircle size={48} style={{ color: 'var(--text-primary)' }} />
            <h2 style={{ marginTop: '1.5rem', fontSize: '1.5rem', fontWeight: 600 }}>Error</h2>
            <p style={{ marginTop: '0.5rem', color: 'var(--text-secondary)' }}>{message}</p>
            <button 
              className="btn btn-secondary" 
              style={{ marginTop: '2rem', width: '100%' }}
              onClick={() => navigate('/login')}
            >
              Back to Sign In
            </button>
          </div>
        )}
      </div>
    </div>
  );
};
