import React, { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { MailCheck, XCircle } from 'lucide-react';
import { api } from '../services/api';
import { motion } from 'framer-motion';

interface VerifyProps {
  onLoginSuccess: (user: any) => void;
}

export const VerifyMagicLink: React.FC<VerifyProps> = ({ onLoginSuccess }) => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [status, setStatus] = useState<'verifying' | 'success' | 'error'>('verifying');
  const [errorMsg, setErrorMsg] = useState('');

  useEffect(() => {
    const token = searchParams.get('token');
    if (!token) {
      setStatus('error');
      setErrorMsg('No token provided in URL');
      return;
    }

    const verify = async () => {
      try {
        const resp = await api.post('/api/v1/auth/passwordless/verify', { token });
        if (resp.data) {
          const meResp = await api.get('/api/v1/auth/me');
          onLoginSuccess(meResp.data);
          setStatus('success');
          setTimeout(() => {
            navigate('/profile');
          }, 1500);
        }
      } catch (err: any) {
        setStatus('error');
        setErrorMsg(err.message || 'The magic link is invalid or has expired.');
      }
    };

    verify();
  }, [searchParams, navigate, onLoginSuccess]);

  return (
    <div className="auth-page">
      <motion.div 
        className="glass-card auth-card flex-col flex-center text-center"
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
      >
        <div className="logo-icon mb-lg">AG</div>
        
        {status === 'verifying' && (
          <>
            <h2 className="text-xl font-bold mb-sm">Verifying Magic Link...</h2>
            <p className="text-secondary">Please wait while we log you in securely.</p>
          </>
        )}

        {status === 'success' && (
          <>
            <MailCheck size={48} className="text-green-500 mb-md" style={{ color: '#10b981' }} />
            <h2 className="text-xl font-bold mb-sm">Success!</h2>
            <p className="text-secondary">Logging you in...</p>
          </>
        )}

        {status === 'error' && (
          <>
            <XCircle size={48} className="text-red-500 mb-md" style={{ color: '#ef4444' }} />
            <h2 className="text-xl font-bold mb-sm">Verification Failed</h2>
            <p className="text-secondary mb-lg">{errorMsg}</p>
            <button className="btn btn-primary" onClick={() => navigate('/login')}>
              Return to Login
            </button>
          </>
        )}
      </motion.div>
    </div>
  );
};
