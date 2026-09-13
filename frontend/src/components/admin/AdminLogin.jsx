import React, { useState } from 'react';
import { ShieldAlert, Lock, User, AlertCircle, ArrowLeft } from 'lucide-react';
import { login } from '../../services/adminApi';

export function AdminLogin({ onLoginSuccess, onBackToDashboard }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!username || !password) {
      setError('Please provide both username and password.');
      return;
    }
    setError(null);
    setLoading(true);

    try {
      const data = await login(username, password);
      onLoginSuccess(data.user);
    } catch (err) {
      setError(err.message || 'Login failed.');
    } finally {
      setLoading(false);
    }
  };

  const handleFillBootstrap = () => {
    setUsername('superadmin');
    setPassword('Admin@Prahari2026!');
  };

  return (
    <div className="admin-login-wrapper">
      <div className="admin-login-card">
        <div className="admin-login-header">
          <div className="brand-logo" style={{ width: 44, height: 44 }}>
            <ShieldAlert style={{ width: 24, height: 24, color: 'var(--accent-teal)' }} />
          </div>
          <h2>PRAHARI<span>-AI</span></h2>
          <p className="admin-login-subtitle">System Administration & Security Control</p>
        </div>

        {error && (
          <div className="admin-login-error">
            <AlertCircle style={{ width: 16, height: 16, flexShrink: 0 }} />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="admin-login-form">
          <div className="form-group">
            <label>Username</label>
            <div className="input-with-icon">
              <User style={{ width: 16, height: 16 }} />
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="Enter username"
                autoFocus
                required
              />
            </div>
          </div>

          <div className="form-group">
            <label>Password</label>
            <div className="input-with-icon">
              <Lock style={{ width: 16, height: 16 }} />
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter password"
                required
              />
            </div>
          </div>

          <button
            type="submit"
            className="btn-admin-primary"
            disabled={loading}
            style={{ marginTop: '0.5rem', width: '100%', height: '40px' }}
          >
            {loading ? 'Authenticating...' : 'Sign In to Admin Panel'}
          </button>
        </form>

        <div className="admin-login-demo-helper">
          <p>Development / Bootstrap Administrator:</p>
          <button type="button" onClick={handleFillBootstrap} className="btn-chip-helper">
            Fill Default Credentials (superadmin)
          </button>
        </div>

        <div className="admin-login-footer">
          <button type="button" onClick={onBackToDashboard} className="btn-link-back">
            <ArrowLeft style={{ width: 14, height: 14 }} />
            <span>Back to Operations Dashboard</span>
          </button>
        </div>
      </div>
    </div>
  );
}
