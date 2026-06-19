import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../services/api';

export const ForgotPassword = () => {
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    setSuccess(false);

    try {
      await api.post('/api/v1/auth/forgot-password', { email });
      setSuccess(true);
      setEmail('');
    } catch (err: any) {
      setError(err.response?.data?.detail || err.response?.data?.error || err.message || 'An error occurred while sending the request');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-card glass-card">
        <div className="page-header" style={{ marginBottom: '1.5rem', textAlign: 'center' }}>
          <h1 className="page-title" style={{ fontSize: '1.75rem' }}>Password Recovery</h1>
          <p className="page-subtitle" style={{ fontSize: '0.9rem' }}>Enter your email to reset your password</p>
        </div>

        {success && (
          <div className="alert alert-success">
            <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0 }}>
              <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
              <polyline points="22 4 12 14.01 9 11.01"></polyline>
            </svg>
            <span>Password reset link sent to your email</span>
          </div>
        )}

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
            <label className="form-label" htmlFor="email">Email Address</label>
            <input
              type="email"
              id="email"
              className="form-input"
              placeholder="name@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>

          <button type="submit" className="btn btn-primary" style={{ width: '100%', marginTop: '1rem' }} disabled={loading}>
            {loading ? 'Sending...' : 'Send Reset Link'}
          </button>
        </form>

        <div className="divider">or</div>
        
        <div style={{ textAlign: 'center' }}>
          <Link to="/login" style={{ color: 'var(--text-primary)', textDecoration: 'none', fontWeight: 600, fontSize: '0.9rem', borderBottom: '1px solid var(--text-primary)', paddingBottom: '2px' }}>
            Back to Sign In
          </Link>
        </div>
      </div>
    </div>
  );
};
