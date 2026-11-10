import { useState } from 'react';
import './LoginScreen.css';
import { API_BASE, safeLocalStorage } from '../utils/constants';
import { SparklesIcon } from './Icons';
import PasswordInput from './PasswordInput';
const storage = safeLocalStorage();

export default function LoginScreen({ onAuthSuccess }) {
  const [isLogin, setIsLogin] = useState(true);
  const [isForgotPassword, setIsForgotPassword] = useState(false);
  const [resetStep, setResetStep] = useState(1);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [email, setEmail] = useState('');
  const [otp, setOtp] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleForgotSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    if (resetStep === 1) {
      if (!email.trim()) {
        setError('Please enter your email.');
        setLoading(false);
        return;
      }
      try {
        const response = await fetch(`${API_BASE}/auth/forgot-password`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email }),
        });
        const data = await response.json();
        if (response.ok) {
          setResetStep(2);
        } else {
          setError(data.detail || 'Failed to send OTP.');
        }
      } catch {
        setError('Network connection error.');
      } finally {
        setLoading(false);
      }
    } else {
      if (!otp.trim() || !password.trim()) {
        setError('Please enter OTP and new password.');
        setLoading(false);
        return;
      }
      try {
        const response = await fetch(`${API_BASE}/auth/reset-password`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email, otp, new_password: password }),
        });
        const data = await response.json();
        if (response.ok) {
          setIsForgotPassword(false);
          setIsLogin(true);
          setOtp('');
          setPassword('');
          setError('');
          setError("Password reset successfully. You can now log in.");
        } else {
          setError(data.detail || 'Failed to reset password.');
        }
      } catch {
        setError('Network connection error.');
      } finally {
        setLoading(false);
      }
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!username.trim() || !password.trim()) {
      setError('Please fill in all fields.');
      return;
    }

    setError('');
    setLoading(true);

    const url = isLogin 
      ? `${API_BASE}/auth/login` 
      : `${API_BASE}/auth/signup`;

    const payload = isLogin 
      ? { username, password } 
      : { username, password, email, otp };

    try {
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      });

      const data = await response.json();

      if (response.ok) {
        storage.setItem('intradoc_token', data.access);
        storage.setItem('intradoc_refresh', data.refresh || '');
        storage.setItem('intradoc_role', data.role);
        storage.setItem('intradoc_department', data.department || 'General');
        onAuthSuccess(data.username, data.role, data.department || 'General');
      } else {
        setError(data.detail || 'Authentication failed.');
      }
    } catch {
      setError('Network connection error. Ensure the Django server is running.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-container">
      <div className="login-card glass-panel">
        <div className="login-header">
          <div className="logo-icon login-logo-icon"><SparklesIcon style={{ width: 20, height: 20 }} /></div>
          <h2 className="login-title">Intradoc AI</h2>
          <p className="login-subtitle">
            {isForgotPassword 
              ? (resetStep === 1 ? 'Reset your password' : 'Enter OTP and new password') 
              : (isLogin ? 'Sign in to access your secure workspace' : 'Create a new corporate account')
            }
          </p>
        </div>

        {error && <div className="login-error">{error}</div>}

        {isForgotPassword ? (
          <form onSubmit={handleForgotSubmit} className="login-form">
            {resetStep === 1 ? (
              <div className="settings-field">
                <label htmlFor="reset-email">Registered Email</label>
                <input
                  id="reset-email"
                  type="email"
                  className="login-input"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@company.com"
                  disabled={loading}
                  required
                />
              </div>
            ) : (
              <>
                <div className="settings-field">
                  <label htmlFor="reset-otp">OTP Code</label>
                  <input
                    id="reset-otp"
                    type="text"
                    className="login-input login-otp-input"
                    value={otp}
                    onChange={(e) => setOtp(e.target.value.replace(/[^0-9]/g, '').slice(0, 6))}
                    placeholder="000000"
                    disabled={loading}
                    maxLength={6}
                    required
                  />
                </div>
                <div className="settings-field" style={{ marginTop: '16px' }}>
                  <label htmlFor="new-password">New Password</label>
                  <PasswordInput
                    id="new-password"
                    className="login-input"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="••••••••"
                    disabled={loading}
                    required
                  />
                </div>
              </>
            )}
            <button type="submit" className="action-btn primary login-submit-btn" disabled={loading}>
              {loading ? 'Processing...' : (resetStep === 1 ? 'Send Reset OTP' : 'Reset Password')}
            </button>
            <div style={{ textAlign: 'center', marginTop: '16px' }}>
              <button
                type="button"
                onClick={() => { setIsForgotPassword(false); setError(''); }}
                className="login-toggle-btn"
              >
                Back to Login
              </button>
            </div>
          </form>
        ) : (
          <form onSubmit={handleSubmit} className="login-form">
            <div className="settings-field">
              <label htmlFor="username">Username</label>
              <input
                id="username"
                type="text"
                className="login-input"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="e.g. jsmith"
                disabled={loading}
                autoComplete="username"
              />
            </div>

            <div className="settings-field" style={{ marginTop: '16px' }}>
              <label htmlFor="password">Password</label>
              <PasswordInput
                id="password"
                className="login-input"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                disabled={loading}
                autoComplete={isLogin ? "current-password" : "new-password"}
              />
              {isLogin && (
                <div style={{ textAlign: 'right', marginTop: '8px' }}>
                  <button
                    type="button"
                    onClick={() => {
                      setIsForgotPassword(true);
                      setResetStep(1);
                      setError('');
                      setPassword('');
                      setOtp('');
                    }}
                    className="login-toggle-btn"
                    style={{ fontSize: '12px', marginLeft: 0 }}
                  >
                    Forgot Password?
                  </button>
                </div>
              )}
            </div>

            {!isLogin && (
              <>
                <div className="settings-field" style={{ marginTop: '16px' }}>
                  <label htmlFor="email">Invitation Email</label>
                  <input
                    id="email"
                    type="email"
                    className="login-input"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="you@company.com"
                    disabled={loading}
                    autoComplete="email"
                  />
                </div>

                <div className="settings-field" style={{ marginTop: '16px' }}>
                  <label htmlFor="otp">OTP Code</label>
                  <input
                    id="otp"
                    type="text"
                    className="login-input login-otp-input"
                    value={otp}
                    onChange={(e) => setOtp(e.target.value.replace(/[^0-9]/g, '').slice(0, 6))}
                    placeholder="000000"
                    disabled={loading}
                    maxLength={6}
                  />
                  <span className="login-otp-hint">
                    Enter the 6-digit code sent to your email by an administrator.
                    First user can leave email & OTP blank to register as Admin.
                  </span>
                </div>
              </>
            )}

            <button
              type="submit"
              className="action-btn primary login-submit-btn"
              disabled={loading}
            >
              {loading ? 'Processing...' : isLogin ? 'Sign In' : 'Create Account'}
            </button>
          </form>
        )}

        {!isForgotPassword && (
          <div className="login-footer">
            <p className="login-footer-text">
              {isLogin ? "Don't have an account?" : "Already have an account?"}
              <button
                onClick={() => {
                  setIsLogin(!isLogin);
                  setError('');
                  setUsername('');
                  setPassword('');
                  setEmail('');
                  setOtp('');
                }}
                className="login-toggle-btn"
              >
                {isLogin ? 'Register now' : 'Sign in instead'}
              </button>
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
