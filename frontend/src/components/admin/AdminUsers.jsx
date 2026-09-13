import React, { useState, useEffect } from 'react';
import {
  Users, Plus, Search, Filter, Edit2, Key, CheckCircle,
  XCircle, AlertCircle, RefreshCw, X, ShieldAlert
} from 'lucide-react';
import {
  fetchAdminUsers, createAdminUser, updateAdminUser, resetUserPassword
} from '../../services/adminApi';

const ROLES = ['SUPER_ADMIN', 'ADMIN', 'SUPERVISOR', 'OFFICER'];

export function AdminUsers({ currentUser }) {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [actionSuccess, setActionSuccess] = useState(null);

  // Filters
  const [searchTerm, setSearchTerm] = useState('');
  const [roleFilter, setRoleFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');

  // Modals state
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [editingUser, setEditingUser] = useState(null);
  const [passwordResetUser, setPasswordResetUser] = useState(null);

  // Forms
  const [formData, setFormData] = useState({
    username: '', password: '', full_name: '', role: 'OFFICER', is_active: 1
  });
  const [newPassword, setNewPassword] = useState('');
  const [modalLoading, setModalLoading] = useState(false);
  const [modalError, setModalError] = useState(null);

  const loadUsers = async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await fetchAdminUsers(
        roleFilter || null,
        statusFilter !== '' ? parseInt(statusFilter) : null
      );
      setUsers(res);
    } catch (err) {
      setError(err.message || 'Failed to load users.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadUsers();
  }, [roleFilter, statusFilter]);

  const handleCreateUser = async (e) => {
    e.preventDefault();
    setModalLoading(true);
    setModalError(null);
    try {
      await createAdminUser(formData);
      setIsAddModalOpen(false);
      setFormData({ username: '', password: '', full_name: '', role: 'OFFICER', is_active: 1 });
      setActionSuccess(`User '${formData.username}' created successfully.`);
      setTimeout(() => setActionSuccess(null), 4000);
      loadUsers();
    } catch (err) {
      setModalError(err.message);
    } finally {
      setModalLoading(false);
    }
  };

  const handleUpdateUser = async (e) => {
    e.preventDefault();
    if (!editingUser) return;
    setModalLoading(true);
    setModalError(null);
    try {
      await updateAdminUser(editingUser.id, {
        full_name: editingUser.full_name,
        role: editingUser.role,
        is_active: editingUser.is_active
      });
      setEditingUser(null);
      setActionSuccess(`User '${editingUser.username}' updated.`);
      setTimeout(() => setActionSuccess(null), 4000);
      loadUsers();
    } catch (err) {
      setModalError(err.message);
    } finally {
      setModalLoading(false);
    }
  };

  const handleResetPassword = async (e) => {
    e.preventDefault();
    if (!passwordResetUser) return;
    setModalLoading(true);
    setModalError(null);
    try {
      await resetUserPassword(passwordResetUser.id, newPassword);
      setPasswordResetUser(null);
      setNewPassword('');
      setActionSuccess(`Password reset for user '${passwordResetUser.username}'.`);
      setTimeout(() => setActionSuccess(null), 4000);
    } catch (err) {
      setModalError(err.message);
    } finally {
      setModalLoading(false);
    }
  };

  const filteredUsers = users.filter((u) => {
    const matchSearch =
      u.username.toLowerCase().includes(searchTerm.toLowerCase()) ||
      u.full_name.toLowerCase().includes(searchTerm.toLowerCase());
    return matchSearch;
  });

  const isSuperAdmin = currentUser?.role === 'SUPER_ADMIN';

  return (
    <div className="admin-page-content">
      <div className="admin-page-header">
        <div>
          <h2>User Accounts & Role Permissions</h2>
          <p className="admin-subtitle">Manage operator identities, access privileges, and account security</p>
        </div>
        <button
          className="btn-admin-primary"
          onClick={() => {
            setModalError(null);
            setIsAddModalOpen(true);
          }}
        >
          <Plus style={{ width: 15, height: 15 }} />
          <span>+ Add New User</span>
        </button>
      </div>

      {actionSuccess && (
        <div className="admin-alert-success">
          <CheckCircle style={{ width: 16, height: 16 }} />
          <span>{actionSuccess}</span>
        </div>
      )}

      {error && (
        <div className="admin-error-box">
          <AlertCircle style={{ width: 18, height: 18 }} />
          <span>{error}</span>
          <button className="btn-admin-secondary" onClick={loadUsers}>Retry</button>
        </div>
      )}

      {/* Filter and Search Bar */}
      <div className="admin-filters-bar">
        <div className="search-input-wrapper">
          <Search style={{ width: 15, height: 15, color: 'var(--text-muted)' }} />
          <input
            type="text"
            placeholder="Search by name or username..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>

        <div className="filter-select-group">
          <select value={roleFilter} onChange={(e) => setRoleFilter(e.target.value)}>
            <option value="">All Roles</option>
            {ROLES.map((r) => (
              <option key={r} value={r}>{r}</option>
            ))}
          </select>

          <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
            <option value="">All Statuses</option>
            <option value="1">Active</option>
            <option value="0">Disabled</option>
          </select>

          <button className="btn-icon-refresh" onClick={loadUsers} title="Refresh Table">
            <RefreshCw style={{ width: 14, height: 14 }} className={loading ? 'spin-icon' : ''} />
          </button>
        </div>
      </div>

      {/* Users Table */}
      <div className="admin-table-wrapper">
        <table className="admin-table">
          <thead>
            <tr>
              <th>Full Name</th>
              <th>Username</th>
              <th>Role</th>
              <th>Status</th>
              <th>Last Login</th>
              <th>Created</th>
              <th style={{ textAlign: 'right' }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {filteredUsers.length === 0 ? (
              <tr>
                <td colSpan={7} className="admin-empty-cell">
                  {loading ? 'Loading users...' : 'No matching users found.'}
                </td>
              </tr>
            ) : (
              filteredUsers.map((u) => (
                <tr key={u.id}>
                  <td><strong>{u.full_name}</strong></td>
                  <td className="mono-cell">{u.username}</td>
                  <td>
                    <span className={`role-badge role-${u.role.toLowerCase()}`}>
                      {u.role}
                    </span>
                  </td>
                  <td>
                    {u.is_active ? (
                      <span className="status-indicator-pill active">
                        <CheckCircle style={{ width: 12, height: 12 }} /> Active
                      </span>
                    ) : (
                      <span className="status-indicator-pill disabled">
                        <XCircle style={{ width: 12, height: 12 }} /> Disabled
                      </span>
                    )}
                  </td>
                  <td className="mono-cell" style={{ fontSize: '0.8rem' }}>
                    {u.last_login || 'Never'}
                  </td>
                  <td className="mono-cell" style={{ fontSize: '0.8rem' }}>
                    {u.created_at ? u.created_at.split(' ')[0] : '-'}
                  </td>
                  <td style={{ textAlign: 'right' }}>
                    <div className="table-actions-group">
                      <button
                        className="btn-action-icon"
                        title="Edit User"
                        onClick={() => {
                          setModalError(null);
                          setEditingUser({ ...u });
                        }}
                      >
                        <Edit2 style={{ width: 14, height: 14 }} />
                      </button>
                      <button
                        className="btn-action-icon"
                        title="Reset Password"
                        onClick={() => {
                          setModalError(null);
                          setNewPassword('');
                          setPasswordResetUser(u);
                        }}
                      >
                        <Key style={{ width: 14, height: 14 }} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* ─── ADD USER MODAL ─── */}
      {isAddModalOpen && (
        <div className="admin-modal-backdrop">
          <div className="admin-modal-box">
            <div className="admin-modal-header">
              <h3>Create User Account</h3>
              <button className="btn-close-modal" onClick={() => setIsAddModalOpen(false)}>
                <X style={{ width: 18, height: 18 }} />
              </button>
            </div>

            {modalError && (
              <div className="admin-login-error" style={{ margin: '0.75rem 1.25rem 0' }}>
                <AlertCircle style={{ width: 15, height: 15 }} />
                <span>{modalError}</span>
              </div>
            )}

            <form onSubmit={handleCreateUser} className="admin-modal-form">
              <div className="form-group">
                <label>Full Name</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Commander Vikram Rao"
                  value={formData.full_name}
                  onChange={(e) => setFormData({ ...formData, full_name: e.target.value })}
                />
              </div>

              <div className="form-group">
                <label>Username</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. officer_rao"
                  value={formData.username}
                  onChange={(e) => setFormData({ ...formData, username: e.target.value })}
                />
              </div>

              <div className="form-group">
                <label>Temporary Password</label>
                <input
                  type="password"
                  required
                  placeholder="Min 6 characters"
                  value={formData.password}
                  onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                />
              </div>

              <div className="form-group">
                <label>Role Assignment</label>
                <select
                  value={formData.role}
                  onChange={(e) => setFormData({ ...formData, role: e.target.value })}
                >
                  {isSuperAdmin && <option value="SUPER_ADMIN">SUPER_ADMIN (Full Control)</option>}
                  <option value="ADMIN">ADMIN (Operations & Configuration)</option>
                  <option value="SUPERVISOR">SUPERVISOR (Incident Triage & Review)</option>
                  <option value="OFFICER">OFFICER (Operations Dashboard Only)</option>
                </select>
              </div>

              <div className="admin-modal-actions">
                <button
                  type="button"
                  className="btn-admin-secondary"
                  onClick={() => setIsAddModalOpen(false)}
                >
                  Cancel
                </button>
                <button type="submit" className="btn-admin-primary" disabled={modalLoading}>
                  {modalLoading ? 'Creating...' : 'Create Account'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ─── EDIT USER MODAL ─── */}
      {editingUser && (
        <div className="admin-modal-backdrop">
          <div className="admin-modal-box">
            <div className="admin-modal-header">
              <h3>Edit User: {editingUser.username}</h3>
              <button className="btn-close-modal" onClick={() => setEditingUser(null)}>
                <X style={{ width: 18, height: 18 }} />
              </button>
            </div>

            {modalError && (
              <div className="admin-login-error" style={{ margin: '0.75rem 1.25rem 0' }}>
                <AlertCircle style={{ width: 15, height: 15 }} />
                <span>{modalError}</span>
              </div>
            )}

            <form onSubmit={handleUpdateUser} className="admin-modal-form">
              <div className="form-group">
                <label>Full Name</label>
                <input
                  type="text"
                  required
                  value={editingUser.full_name}
                  onChange={(e) => setEditingUser({ ...editingUser, full_name: e.target.value })}
                />
              </div>

              <div className="form-group">
                <label>Role</label>
                <select
                  value={editingUser.role}
                  onChange={(e) => setEditingUser({ ...editingUser, role: e.target.value })}
                  disabled={!isSuperAdmin && editingUser.role === 'SUPER_ADMIN'}
                >
                  {isSuperAdmin && <option value="SUPER_ADMIN">SUPER_ADMIN</option>}
                  <option value="ADMIN">ADMIN</option>
                  <option value="SUPERVISOR">SUPERVISOR</option>
                  <option value="OFFICER">OFFICER</option>
                </select>
              </div>

              <div className="form-group">
                <label>Account Status</label>
                <select
                  value={editingUser.is_active}
                  onChange={(e) => setEditingUser({ ...editingUser, is_active: parseInt(e.target.value) })}
                >
                  <option value={1}>Active</option>
                  <option value={0}>Disabled</option>
                </select>
              </div>

              <div className="admin-modal-actions">
                <button
                  type="button"
                  className="btn-admin-secondary"
                  onClick={() => setEditingUser(null)}
                >
                  Cancel
                </button>
                <button type="submit" className="btn-admin-primary" disabled={modalLoading}>
                  {modalLoading ? 'Saving...' : 'Save Changes'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ─── RESET PASSWORD MODAL ─── */}
      {passwordResetUser && (
        <div className="admin-modal-backdrop">
          <div className="admin-modal-box">
            <div className="admin-modal-header">
              <h3>Reset Password: {passwordResetUser.username}</h3>
              <button className="btn-close-modal" onClick={() => setPasswordResetUser(null)}>
                <X style={{ width: 18, height: 18 }} />
              </button>
            </div>

            {modalError && (
              <div className="admin-login-error" style={{ margin: '0.75rem 1.25rem 0' }}>
                <AlertCircle style={{ width: 15, height: 15 }} />
                <span>{modalError}</span>
              </div>
            )}

            <form onSubmit={handleResetPassword} className="admin-modal-form">
              <div className="form-group">
                <label>New Password</label>
                <input
                  type="password"
                  required
                  placeholder="Min 6 characters"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                />
              </div>

              <div className="admin-modal-actions">
                <button
                  type="button"
                  className="btn-admin-secondary"
                  onClick={() => setPasswordResetUser(null)}
                >
                  Cancel
                </button>
                <button type="submit" className="btn-admin-primary" disabled={modalLoading}>
                  {modalLoading ? 'Resetting...' : 'Set Password'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
