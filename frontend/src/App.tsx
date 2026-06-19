import React, { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { api } from './services/api';
import { Layout } from './components/Layout';
import { Login } from './pages/Login';
import { Profile } from './pages/Profile';
import { Admin } from './pages/Admin';
import { Organization } from './pages/Organization';
import { ForgotPassword } from './pages/ForgotPassword';
import { ResetPassword } from './pages/ResetPassword';
import { VerifyEmail } from './pages/VerifyEmail';
export const App: React.FC = () => {
  const [user, setUser] = useState<any>(null);
  const [checkingSession, setCheckingSession] = useState(true);

  // Restore session on application mount
  const restoreSession = async () => {
    try {
      const resp = await api.get('/api/v1/auth/me');
      setUser(resp.data);
    } catch (err) {
      console.log('No active session found.');
      setUser(null);
    } finally {
      setCheckingSession(false);
    }
  };

  useEffect(() => {
    restoreSession();
  }, []);

  const handleLoginSuccess = (userData: any) => {
    setUser(userData);
  };

  const handleLogout = () => {
    setUser(null);
  };

  if (checkingSession) {
    return (
      <div className="flex-center" style={{ minHeight: '100vh', background: 'var(--bg-main)' }}>
        <div className="flex-col flex-center gap-xl">
          <div style={{ position: 'relative', width: '80px', height: '80px' }} className="flex-center">
            {/* Outer glowing rings */}
            <motion.div
              animate={{ rotate: 360 }}
              transition={{ repeat: Infinity, duration: 2, ease: 'linear' }}
              style={{
                position: 'absolute',
                top: 0, left: 0, right: 0, bottom: 0,
                borderRadius: '50%',
                border: '3px solid transparent',
                borderTopColor: 'var(--primary-color)',
                borderRightColor: 'var(--primary-color)',
                boxShadow: '0 0 20px rgba(139, 92, 246, 0.5)',
                opacity: 0.8
              }}
            />
            <motion.div
              animate={{ rotate: -360 }}
              transition={{ repeat: Infinity, duration: 3, ease: 'linear' }}
              style={{
                position: 'absolute',
                top: '-10px', left: '-10px', right: '-10px', bottom: '-10px',
                borderRadius: '50%',
                border: '2px dashed var(--primary-color)',
                opacity: 0.3
              }}
            />
            {/* Inner pulsing logo */}
            <motion.div 
              animate={{ scale: [0.95, 1.05, 0.95], opacity: [0.8, 1, 0.8] }}
              transition={{ repeat: Infinity, duration: 2, ease: 'easeInOut' }}
              className="logo-icon"
              style={{
                width: '60px',
                height: '60px',
                fontSize: '1.5rem',
                margin: 0,
                boxShadow: '0 0 15px rgba(139, 92, 246, 0.4)'
              }}
            >
              AG
            </motion.div>
          </div>
          <motion.p 
            animate={{ opacity: [0.5, 1, 0.5] }}
            transition={{ repeat: Infinity, duration: 2, ease: 'easeInOut' }}
            style={{ 
              color: 'var(--primary-color)', 
              fontSize: '0.9rem',
              letterSpacing: '3px',
              fontWeight: 600,
              textTransform: 'uppercase',
              textShadow: '0 0 10px rgba(139, 92, 246, 0.3)'
            }}
          >
            Restoring session...
          </motion.p>
        </div>
      </div>
    );
  }

  // --- Route Guards ---

  // Requires user to be logged in
  const ProtectedRoute = ({ children }: { children: React.ReactNode }) => {
    if (!user) {
      return <Navigate to="/login" replace />;
    }
    return <Layout user={user} onLogout={handleLogout}>{children}</Layout>;
  };

  // Requires user to be logged in AND have admin role
  const AdminRoute = ({ children }: { children: React.ReactNode }) => {
    if (!user) {
      return <Navigate to="/login" replace />;
    }
    if (user.role !== 'admin') {
      return <Navigate to="/profile" replace />;
    }
    return <Layout user={user} onLogout={handleLogout}>{children}</Layout>;
  };

  // Requires user to be logged out (e.g. login/register pages)
  const GuestRoute = ({ children }: { children: React.ReactNode }) => {
    if (user) {
      return <Navigate to="/profile" replace />;
    }
    return <>{children}</>;
  };

  return (
    <BrowserRouter>
      <Routes>
        <Route
          path="/login"
          element={
            <GuestRoute>
              <Login onLoginSuccess={handleLoginSuccess} />
            </GuestRoute>
          }
        />
        <Route
          path="/forgot-password"
          element={
            <GuestRoute>
              <ForgotPassword />
            </GuestRoute>
          }
        />
        <Route
          path="/reset-password"
          element={<ResetPassword />}
        />
        <Route
          path="/verify-email"
          element={<VerifyEmail />}
        />
        <Route
          path="/profile"
          element={
            <ProtectedRoute>
              <Profile />
            </ProtectedRoute>
          }
        />
        <Route
          path="/admin"
          element={
            <AdminRoute>
              <Admin />
            </AdminRoute>
          }
        />
        <Route
          path="/organization"
          element={
            <AdminRoute>
              <Organization />
            </AdminRoute>
          }
        />
        {/* Default redirect to profile or login */}
        <Route path="*" element={<Navigate to={user ? '/profile' : '/login'} replace />} />
      </Routes>
    </BrowserRouter>
  );
};

export default App;
