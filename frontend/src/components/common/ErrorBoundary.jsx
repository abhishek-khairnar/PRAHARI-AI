import React from 'react';
import { ShieldAlert, RefreshCw, ArrowLeft, LayoutDashboard } from 'lucide-react';

export class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error('[PRAHARI-AI ErrorBoundary] Uncaught runtime exception:', error, errorInfo);
    this.setState({ errorInfo });
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null, errorInfo: null });
    if (this.props.onRetry) {
      this.props.onRetry();
    }
  };

  render() {
    if (this.state.hasError) {
      const isDev = Boolean(import.meta.env?.DEV);

      return (
        <div className="admin-error-boundary-container" style={{
          minHeight: '60vh',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '2rem',
          backgroundColor: 'transparent'
        }}>
          <div style={{
            maxWidth: '560px',
            width: '100%',
            backgroundColor: 'var(--bg-card, #1e293b)',
            border: '1px solid var(--border-main, #334155)',
            borderRadius: '12px',
            padding: '2rem',
            boxShadow: '0 10px 25px rgba(0, 0, 0, 0.5)',
            textAlign: 'center'
          }}>
            <div style={{
              width: '48px',
              height: '48px',
              margin: '0 auto 1rem',
              borderRadius: '50%',
              backgroundColor: 'rgba(239, 68, 68, 0.15)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#ef4444'
            }}>
              <ShieldAlert style={{ width: 28, height: 28 }} />
            </div>

            <h2 style={{
              fontSize: '1.25rem',
              fontWeight: 700,
              color: 'var(--text-main, #f8fafc)',
              marginBottom: '0.5rem'
            }}>
              PRAHARI-AI
            </h2>

            <p style={{
              fontSize: '0.95rem',
              color: 'var(--text-muted, #94a3b8)',
              marginBottom: '1.5rem'
            }}>
              Something went wrong loading this page.
            </p>

            {isDev && this.state.error && (
              <div style={{
                textAlign: 'left',
                backgroundColor: 'rgba(0, 0, 0, 0.3)',
                border: '1px solid rgba(239, 68, 68, 0.2)',
                borderRadius: '6px',
                padding: '0.75rem 1rem',
                marginBottom: '1.5rem',
                maxHeight: '180px',
                overflowY: 'auto',
                fontFamily: 'monospace',
                fontSize: '0.8rem',
                color: '#fca5a5'
              }}>
                <div style={{ fontWeight: 600, marginBottom: '0.25rem' }}>
                  {this.state.error.toString()}
                </div>
                {this.state.errorInfo?.componentStack && (
                  <pre style={{ margin: 0, whiteSpace: 'pre-wrap', opacity: 0.8, fontSize: '0.75rem' }}>
                    {this.state.errorInfo.componentStack}
                  </pre>
                )}
              </div>
            )}

            <div style={{
              display: 'flex',
              flexWrap: 'wrap',
              gap: '0.75rem',
              justifyContent: 'center'
            }}>
              <button
                className="btn-admin-primary"
                onClick={this.handleRetry}
                style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}
              >
                <RefreshCw style={{ width: 14, height: 14 }} />
                <span>Retry</span>
              </button>

              <button
                className="btn-admin-secondary"
                onClick={() => { window.location.href = '/admin'; }}
                style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}
              >
                <LayoutDashboard style={{ width: 14, height: 14 }} />
                <span>Return to Admin Overview</span>
              </button>

              <button
                className="btn-admin-secondary"
                onClick={() => { window.location.href = '/'; }}
                style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}
              >
                <ArrowLeft style={{ width: 14, height: 14 }} />
                <span>Operations Dashboard</span>
              </button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
