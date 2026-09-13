import React, { useState, useEffect } from 'react';
import { ShieldAlert, Lock, User, AlertCircle, ArrowLeft, KeyRound, CheckCircle } from 'lucide-react';
import { login, fetchAuthContext, changePassword } from '../../services/adminApi';

export function AdminLogin({ onLoginSuccess, onBackToDashboard }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [authContext, setAuthContext] = useState({ is_development: false, allow_demo_credentials: false });

  // First-time password rotation state
  const [mustRotatePassword, setMustRotatePassword] = useState(false);
  const [pendingUser, setPendingUser] = useState(null);
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [rotationSuccess, setRotationSuccess] = useState(false);

  useEffect(() => {
    fetchAuthContext().then(ctx => {
      if (ctx) setAuthContext(ctx);
    });
  }, []);

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
      if (data.user?.must_change_password) {
        setPendingUser(data.user);
        setMustRotatePassword(true);
      } else {
        onLoginSuccess(data.user);
      }
    } catch (err) {
      setError(err.message || 'Authentication failed. Please verify credentials.');
    } finally {
      setLoading(false);
    }
  };

  const handlePasswordRotation = async (e) => {
    e.preventDefault();
    if (newPassword.length < 8) {
      setError('New password must be at least 8 characters long.');
      return;
    }
    if (newPassword !== confirmPassword) {
      setError('New password and confirmation do not match.');
      return;
    }
    if (newPassword === password) {
      setError('New password must be different from current temporary password.');
      return;
    }

    setError(null);
    setLoading(true);

    try {
      await changePassword(password, newPassword);
      setRotationSuccess(true);
      setTimeout(() => {
        const updated = { ...pendingUser, must_change_password: 0 };
        onLoginSuccess(updated);
      }, 1200);
    } catch (err) {
      setError(err.message || 'Password update failed. Please try again.');
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
          <p className="admin-login-subtitle">
            {mustRotatePassword ? 'Mandatory First-Time Password Rotation' : 'System Administration & Security Control'}
          </p>
        </div>

        {error && (
          <div className="admin-login-error">
            <AlertCircle style={{ width: 16, height: 16, flexShrink: 0 }} />
            <span>{error}</span>
          </div>
        )}

        {rotationSuccess && (
          <div className="admin-alert-success">
            <CheckCircle style={{ width: 16, height: 16, flexShrink: 0 }} />
            <span>Password updated securely. Redirecting to Admin Console...</span>
          </div>
        )}

        {!mustRotatePassword ? (
          <>
            <form onSubmit={handleSubmit} className="admin-login-form">
              <div className="form-group">
                <label>Administrative Username</label>
                <div className="input-with-icon">
                  <User style={{ width: 16, height: 16 }} />
                  <input
                    type="text"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    placeholder="Enter admin username"
                    autoFocus
                    required
                    disabled={loading}
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
                    disabled={loading}
                  />
                </div>
              </div>

              <button
                type="submit"
                className="btn-admin-primary"
                disabled={loading}
                style={{ marginTop: '0.5rem', width: '100%', height: '40px' }}
              >
                {loading ? 'Authenticating...' : 'Sign In Securely'}
              </button>
            </form>

            {authContext.allow_demo_credentials && (
              <div className="admin-login-demo-helper">
                <p style={{ color: 'var(--accent-teal)' }}>DEVELOPMENT / LOCAL DEMO ONLY</p>
                <button type="button" onClick={handleFillBootstrap} className="btn-chip-helper">
                  Fill Default Credentials (superadmin)
                </button>
              </div>
            )}

            {!authContext.allow_demo_credentials && (
              <div style={{ textAlign: 'center', fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                Protected administrative access. Authorized personnel only.
              </div>
            )}
          </>
        ) : (
          <form onSubmit={handlePasswordRotation} className="admin-login-form">
            <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', lineHeight: '1.4' }}>
              Welcome <strong style={{ color: 'var(--text-main)' }}>{pendingUser?.username}</strong>. A temporary or bootstrap password was used. For security, you must set a permanent password before continuing.
            </div>

            <div className="form-group">
              <label>New Password (min 8 characters)</label>
              <div className="input-with-icon">
                <KeyRound style={{ width: 16, height: 16 }} />
                <input
                  type="password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  placeholder="Enter new strong password"
                  autoFocus
                  required
                  disabled={loading || rotationSuccess}
                />
              </div>
            </div>

            <div className="form-group">
              <label>Confirm New Password</label>
              <div className="input-with-icon">
                <Lock style={{ width: 16, height: 16 }} />
                <input
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="Re-enter new password"
                  required
                  disabled={loading || rotationSuccess}
                />
              </div>
            </div>

            <button
              type="submit"
              className="btn-admin-primary"
              disabled={loading || rotationSuccess}
              style={{ marginTop: '0.5rem', width: '100%', height: '40px' }}
            >
              {loading ? 'Updating Password...' : 'Save New Password & Continue'}
            </button>
          </form>
        )}

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
