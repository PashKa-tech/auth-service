import React, { useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Mail, Lock, CheckCircle, AlertCircle, ArrowRight } from 'lucide-react';
import { api } from '../services/api';
import { motion } from 'framer-motion';

export const InviteAccept: React.FC = () => {
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token');
  const navigate = useNavigate();

  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);

  if (!token) {
    return (
      <div className="flex-center" style={{ minHeight: '80vh', flexDirection: 'column', gap: '1rem' }}>
        <AlertCircle size={48} color="var(--danger-color)" />
        <h2>Invalid Invitation Link</h2>
        <p style={{ color: 'var(--text-secondary)' }}>This invitation link is missing the token.</p>
        <button className="btn btn-primary" onClick={() => navigate('/login')}>Go to Login</button>
      </div>
    );
  }

  const handleAccept = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!password) {
      setError('Please enter a password');
      return;
    }

    setError('');
    setLoading(true);

    try {
      await api.post('/api/v1/organizations/invites/accept', { token, password });
      setSuccess(true);
      setTimeout(() => {
        navigate('/login');
      }, 3000);
    } catch (err: any) {
      setError(err.message || 'Failed to accept invitation. It may be expired or invalid.');
    } finally {
      setLoading(false);
    }
  };

  if (success) {
    return (
      <div className="flex-center" style={{ minHeight: '80vh' }}>
        <motion.div 
          className="glass-card" 
          style={{ maxWidth: '400px', width: '100%', textAlign: 'center' }}
          initial={{ scale: 0.9, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
        >
          <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '1.5rem', color: 'var(--success)' }}>
            <CheckCircle size={48} />
          </div>
          <h2 style={{ marginBottom: '1rem' }}>Invitation Accepted!</h2>
          <p style={{ color: 'var(--text-secondary)', marginBottom: '1.5rem' }}>
            Your account has been successfully created. Redirecting to login...
          </p>
        </motion.div>
      </div>
    );
  }

  return (
    <div className="flex-center" style={{ minHeight: '80vh' }}>
      <motion.div 
        className="glass-card" 
        style={{ maxWidth: '400px', width: '100%' }}
        initial={{ y: 20, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
      >
        <div style={{ textAlign: 'center', marginBottom: '2rem' }}>
          <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '1rem', color: 'var(--primary-color)' }}>
            <Mail size={48} />
          </div>
          <h2>Join Organization</h2>
          <p style={{ color: 'var(--text-secondary)', marginTop: '0.5rem' }}>
            Set a password for your new account to accept the invitation.
          </p>
        </div>

        {error && (
          <div className="alert alert-error" style={{ marginBottom: '1.5rem' }}>
            <AlertCircle size={20} />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleAccept}>
          <div className="form-group">
            <label>Password</label>
            <div style={{ position: 'relative' }}>
              <Lock size={20} style={{ position: 'absolute', left: '1rem', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
              <input
                type="password"
                className="form-input"
                style={{ paddingLeft: '3rem' }}
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={8}
              />
            </div>
          </div>

          <button 
            type="submit" 
            className="btn btn-primary" 
            style={{ width: '100%', marginTop: '1rem', justifyContent: 'center' }}
            disabled={loading}
          >
            {loading ? 'Processing...' : (
              <>
                Accept Invitation <ArrowRight size={18} />
              </>
            )}
          </button>
        </form>
      </motion.div>
    </div>
  );
};
