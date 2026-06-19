import React from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { Shield, LogOut, User } from 'lucide-react';
import { api } from '../services/api';

interface LayoutProps {
  children: React.ReactNode;
  user: {
    id: string;
    email: string;
    role: string;
  } | null;
  onLogout: () => void;
}

export const Layout: React.FC<LayoutProps> = ({ children, user, onLogout }) => {
  const location = useLocation();
  const navigate = useNavigate();

  const handleSignOut = async () => {
    try {
      await api.post('/api/v1/auth/logout');
    } catch (err) {
      console.error('Logout request failed', err);
    } finally {
      onLogout();
      navigate('/login');
    }
  };

  const isAdmin = user?.role === 'admin';

  return (
    <div className="dashboard-container">
      <aside className="sidebar">
        <div>
          <div className="logo-container">
            <div className="logo-icon">AG</div>
            <span className="logo-text">Auth Service</span>
          </div>

          <nav className="nav-list">
            <Link
              to="/profile"
              className={`nav-item ${location.pathname === '/profile' ? 'active' : ''}`}
            >
              <User size={20} />
              <span className="nav-label">Profile Settings</span>
            </Link>

            {isAdmin && (
              <Link
                to="/admin"
                className={`nav-item ${location.pathname === '/admin' ? 'active' : ''}`}
              >
                <Shield size={20} />
                <span className="nav-label">Admin Dashboard</span>
              </Link>
            )}
          </nav>
        </div>

        <div className="flex flex-col gap-md">
          {user && (
            <div className="flex flex-col gap-sm" style={{ padding: '0 0.5rem' }}>
              <span className="logo-text" style={{ fontSize: '0.9rem', fontWeight: 600, textTransform: 'none', letterSpacing: '0' }}>
                {user.email.split('@')[0]}
              </span>
              <span className="badge badge-purple" style={{ alignSelf: 'flex-start' }}>
                {user.role}
              </span>
            </div>
          )}
          <button onClick={handleSignOut} className="btn btn-secondary" style={{ width: '100%', justifyContent: 'flex-start' }}>
            <LogOut size={16} />
            <span className="nav-label">Sign Out</span>
          </button>
        </div>
      </aside>

      <main className="main-content">
        <AnimatePresence mode="wait">
          <motion.div
            key={location.pathname}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ duration: 0.2 }}
          >
            {children}
          </motion.div>
        </AnimatePresence>
      </main>
    </div>
  );
};
