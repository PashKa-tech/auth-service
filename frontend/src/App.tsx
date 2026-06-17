import React, { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { api } from './services/api';
import { Layout } from './components/Layout';
import { Login } from './pages/Login';
import { Profile } from './pages/Profile';
import { Admin } from './pages/Admin';

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
        <div className="flex-col flex-center gap-md">
          <div className="logo-icon animate-pulse-slow">AG</div>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>Восстановление сессии...</p>
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
        {/* Default redirect to profile or login */}
        <Route path="*" element={<Navigate to={user ? '/profile' : '/login'} replace />} />
      </Routes>
    </BrowserRouter>
  );
};

export default App;
