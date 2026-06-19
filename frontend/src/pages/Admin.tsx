import React, { useState, useEffect } from 'react';
import { Users, ShieldAlert, Layers, Search, FileText, Globe } from 'lucide-react';
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { api } from '../services/api';

const activeUsersData = [
  { name: 'Mon', users: 400 },
  { name: 'Tue', users: 300 },
  { name: 'Wed', users: 550 },
  { name: 'Thu', users: 450 },
  { name: 'Fri', users: 700 },
  { name: 'Sat', users: 650 },
  { name: 'Sun', users: 800 },
];

const loginsPerDayData = [
  { name: 'Mon', logins: 1200 },
  { name: 'Tue', logins: 1100 },
  { name: 'Wed', logins: 1500 },
  { name: 'Thu', logins: 1400 },
  { name: 'Fri', logins: 1800 },
  { name: 'Sat', logins: 1600 },
  { name: 'Sun', logins: 1900 },
];

export const Admin: React.FC = () => {
  const [stats, setStats] = useState<any>({ users_count: 0, sessions_count: 0, anomaly_count: 0 });
  const [users, setUsers] = useState<any[]>([]);
  const [logs, setLogs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [activeTab, setActiveTab] = useState<'users' | 'logs' | 'analytics'>('users');

  // Local filter states
  const [userSearch, setUserSearch] = useState('');
  const [logSearch, setLogSearch] = useState('');

  const [userLimit, setUserLimit] = useState(100);
  const [logLimit, setLogLimit] = useState(100);

  const fetchAdminData = async () => {
    try {
      const statsResp = await api.get('/api/v1/auth/admin/stats');
      setStats(statsResp.data);

      const usersResp = await api.get(`/api/v1/auth/admin/users?limit=${userLimit}`);
      setUsers(usersResp.data);

      const logsResp = await api.get(`/api/v1/auth/admin/audit-logs?limit=${logLimit}`);
      setLogs(logsResp.data);
    } catch (err: any) {
      setError(err.message || 'Ошибка доступа или загрузки данных админ-панели');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAdminData();
  }, [userLimit, logLimit]);

  if (loading) {
    return <div className="flex-center" style={{ minHeight: '50vh' }}>Загрузка панели управления...</div>;
  }

  // Filter users
  const filteredUsers = users.filter((u) => 
    u.email.toLowerCase().includes(userSearch.toLowerCase()) ||
    u.role.toLowerCase().includes(userSearch.toLowerCase())
  );

  // Filter audit logs
  const filteredLogs = logs.filter((l) => 
    l.action.toLowerCase().includes(logSearch.toLowerCase()) ||
    (l.ip_address && l.ip_address.includes(logSearch)) ||
    (l.user_agent && l.user_agent.toLowerCase().includes(logSearch.toLowerCase()))
  );

  return (
    <div>
      {/* Page Header */}
      <div className="page-header">
        <h1 className="page-title">Административная панель</h1>
        <p className="page-subtitle">Общий контроль безопасности, мониторинг активности и журналы аудита</p>
      </div>

      {error && (
        <div className="alert alert-error">
          <ShieldAlert size={20} />
          <span>{error}</span>
        </div>
      )}

      {/* Stats Cards Row */}
      <div className="grid-3" style={{ marginBottom: '2.5rem' }}>
        
        {/* Total Users */}
        <div className="glass-card flex align-center gap-lg" style={{ padding: '1.5rem' }}>
          <div className="logo-icon" style={{ background: 'var(--grad-primary)' }}>
            <Users size={20} />
          </div>
          <div>
            <span style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>Всего пользователей</span>
            <h3 style={{ fontSize: '1.75rem', fontWeight: 700, marginTop: '0.25rem' }}>{stats.users_count}</h3>
          </div>
        </div>

        {/* Active Sessions */}
        <div className="glass-card flex align-center gap-lg" style={{ padding: '1.5rem' }}>
          <div className="logo-icon" style={{ background: 'var(--grad-secondary)' }}>
            <Layers size={20} />
          </div>
          <div>
            <span style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>Активных сеансов</span>
            <h3 style={{ fontSize: '1.75rem', fontWeight: 700, marginTop: '0.25rem' }}>{stats.sessions_count}</h3>
          </div>
        </div>

        {/* Anomalies detected */}
        <div className="glass-card flex align-center gap-lg" style={{ padding: '1.5rem' }}>
          <div className="logo-icon" style={{ background: stats.anomaly_count > 0 ? 'var(--grad-danger)' : 'var(--grad-success)' }}>
            <ShieldAlert size={20} />
          </div>
          <div>
            <span style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>Выявлено аномалий</span>
            <h3 style={{ fontSize: '1.75rem', fontWeight: 700, marginTop: '0.25rem' }}>{stats.anomaly_count}</h3>
          </div>
        </div>

      </div>

      {/* Tabs */}
      <div className="flex gap-md" style={{ marginBottom: '1.5rem' }}>
        <button 
          className={`btn ${activeTab === 'users' ? 'btn-primary' : 'btn-secondary'}`} 
          onClick={() => setActiveTab('users')}
          style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}
        >
          <Users size={16} /> Пользователи
        </button>
        <button 
          className={`btn ${activeTab === 'logs' ? 'btn-primary' : 'btn-secondary'}`} 
          onClick={() => setActiveTab('logs')}
          style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}
        >
          <FileText size={16} /> Журналы
        </button>
        <button 
          className={`btn ${activeTab === 'analytics' ? 'btn-primary' : 'btn-secondary'}`} 
          onClick={() => setActiveTab('analytics')}
          style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}
        >
          <Layers size={16} /> Аналитика
        </button>
      </div>

      {/* User Management Section */}
      {activeTab === 'users' && (
      <div className="glass-card" style={{ marginBottom: '2.5rem' }}>
        <div className="flex justify-between align-center" style={{ marginBottom: '1.5rem', flexWrap: 'wrap', gap: '1rem' }}>
          <h2 style={{ fontSize: '1.25rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Users size={20} /> Список пользователей
          </h2>
          <div style={{ position: 'relative', width: '280px' }}>
            <Search size={16} style={{ position: 'absolute', left: '10px', top: '12px', color: 'var(--text-muted)' }} />
            <input
              type="text"
              placeholder="Поиск пользователей..."
              className="form-input"
              style={{ paddingLeft: '2.5rem', fontSize: '0.9rem', width: '100%' }}
              value={userSearch}
              onChange={(e) => setUserSearch(e.target.value)}
            />
          </div>
        </div>

        <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>Email</th>
                <th>Роль</th>
                <th>2FA</th>
                <th>Email верифицирован</th>
                <th>Статус аккаунта</th>
              </tr>
            </thead>
            <tbody>
              {filteredUsers.map((u) => (
                <tr key={u.id}>
                  <td style={{ fontWeight: 600 }}>{u.email}</td>
                  <td>
                    <span className="badge badge-purple">{u.role}</span>
                  </td>
                  <td>
                    <span className={u.two_factor_enabled ? 'badge badge-green' : 'badge badge-red'}>
                      {u.two_factor_enabled ? 'Да' : 'Нет'}
                    </span>
                  </td>
                  <td>
                    <span className={u.is_verified ? 'badge badge-green' : 'badge badge-red'}>
                      {u.is_verified ? 'Да' : 'Нет'}
                    </span>
                  </td>
                  <td>
                    <span className={u.is_active ? 'badge badge-green' : 'badge badge-red'}>
                      {u.is_active ? 'Активен' : 'Отключен'}
                    </span>
                  </td>
                </tr>
              ))}
              {filteredUsers.length === 0 && (
                <tr>
                  <td colSpan={5} style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)' }}>
                    Пользователи не найдены
                  </td>
                </tr>
              )}
            </tbody>
          </table>
          
          {users.length >= userLimit && (
            <div style={{ padding: '1rem', textAlign: 'center' }}>
              <button 
                className="btn btn-secondary" 
                onClick={() => setUserLimit(prev => prev + 100)}
              >
                Загрузить еще
              </button>
            </div>
          )}
        </div>
      </div>
      )}

      {/* Audit Logs Section */}
      {activeTab === 'logs' && (
      <div className="glass-card">
        <div className="flex justify-between align-center" style={{ marginBottom: '1.5rem', flexWrap: 'wrap', gap: '1rem' }}>
          <h2 style={{ fontSize: '1.25rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <FileText size={20} /> Журнал аудита событий (Logs)
          </h2>
          <div style={{ position: 'relative', width: '280px' }}>
            <Search size={16} style={{ position: 'absolute', left: '10px', top: '12px', color: 'var(--text-muted)' }} />
            <input
              type="text"
              placeholder="Поиск по событиям/IP..."
              className="form-input"
              style={{ paddingLeft: '2.5rem', fontSize: '0.9rem', width: '100%' }}
              value={logSearch}
              onChange={(e) => setLogSearch(e.target.value)}
            />
          </div>
        </div>

        <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>Событие (Action)</th>
                <th>IP-адрес</th>
                <th>Устройство / Браузер</th>
                <th>Дата и время</th>
                <th>Дополнительно</th>
              </tr>
            </thead>
            <tbody>
              {filteredLogs.map((l) => (
                <tr key={l.id}>
                  <td style={{ fontWeight: 600 }}>
                    <span className={l.action.includes('fail') || l.action.includes('anomaly') ? 'badge badge-red' : 'badge badge-blue'}>
                      {l.action}
                    </span>
                  </td>
                  <td>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                      <Globe size={14} style={{ color: 'var(--text-secondary)' }} />
                      <span>{l.ip_address || 'system'}</span>
                    </div>
                  </td>
                  <td style={{ maxWidth: '240px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={l.user_agent}>
                    {l.user_agent || 'N/A'}
                  </td>
                  <td>{new Date(l.timestamp).toLocaleString()}</td>
                  <td>
                    {l.metadata ? (
                      <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', fontFamily: 'monospace' }}>
                        {JSON.stringify(l.metadata)}
                      </span>
                    ) : (
                      <span style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>-</span>
                    )}
                  </td>
                </tr>
              ))}
              {filteredLogs.length === 0 && (
                <tr>
                  <td colSpan={5} style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)' }}>
                    Журнал пуст
                  </td>
                </tr>
              )}
            </tbody>
          </table>

          {logs.length >= logLimit && (
            <div style={{ padding: '1rem', textAlign: 'center' }}>
              <button 
                className="btn btn-secondary" 
                onClick={() => setLogLimit(prev => prev + 100)}
              >
                Загрузить еще
              </button>
            </div>
          )}
        </div>
      </div>
      )}

      {/* Analytics Section */}
      {activeTab === 'analytics' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
          <div className="glass-card" style={{ padding: '1.5rem' }}>
            <h2 style={{ fontSize: '1.25rem', marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Users size={20} /> Active Users
            </h2>
            <div style={{ width: '100%', height: 350 }}>
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={activeUsersData} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
                  <XAxis dataKey="name" stroke="var(--text-secondary)" />
                  <YAxis stroke="var(--text-secondary)" />
                  <Tooltip 
                    contentStyle={{ backgroundColor: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: '8px' }}
                    itemStyle={{ color: 'var(--text-primary)' }}
                  />
                  <Legend />
                  <Line type="monotone" dataKey="users" stroke="#8b5cf6" strokeWidth={3} activeDot={{ r: 8 }} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="glass-card" style={{ padding: '1.5rem' }}>
            <h2 style={{ fontSize: '1.25rem', marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Layers size={20} /> Logins per day
            </h2>
            <div style={{ width: '100%', height: 350 }}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={loginsPerDayData} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
                  <XAxis dataKey="name" stroke="var(--text-secondary)" />
                  <YAxis stroke="var(--text-secondary)" />
                  <Tooltip 
                    contentStyle={{ backgroundColor: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: '8px' }}
                    itemStyle={{ color: 'var(--text-primary)' }}
                  />
                  <Legend />
                  <Bar dataKey="logins" fill="#ec4899" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
