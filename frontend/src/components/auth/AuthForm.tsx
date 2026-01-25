import React, { useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import { useLocation, useNavigate } from 'react-router-dom';
import { AlertCircle, Loader2 } from 'lucide-react';

export default function AuthForm() {
  const { login, register } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [isLogin, setIsLogin] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    const from = (location.state as { from?: { pathname?: string } })?.from?.pathname || '/app';

    try {
      if (isLogin) {
        await login({ email, password });
      } else {
        if (password !== confirmPassword) {
          setError("Passwords do not match");
          setLoading(false);
          return;
        }
        await register({ email, password, full_name: fullName });
      }
      navigate(from, { replace: true });
    } catch (err: any) {
      console.error("Auth error:", err);
      setError(err.message || "Authentication failed. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const switchMode = (loginMode: boolean) => {
    setIsLogin(loginMode);
    setError(null);
  };

  return (
    <div className="auth-form-container">
      <div className="auth-form-card glass-card animate-fade-in-up">
        {/* Mobile logo - only shows on small screens */}
        <div className="auth-mobile-header hide-desktop">
          <h1 className="auth-mobile-logo">AIlingva</h1>
          <p className="auth-mobile-tagline">Master English with AI</p>
        </div>

        {/* Tabs */}
        <div className="tabs mb-6">
          <button
            className={`tab ${isLogin ? 'tab-active' : ''}`}
            onClick={() => switchMode(true)}
            type="button"
          >
            Log In
          </button>
          <button
            className={`tab ${!isLogin ? 'tab-active' : ''}`}
            onClick={() => switchMode(false)}
            type="button"
          >
            Sign Up
          </button>
        </div>

        {/* Error message */}
        {error && (
          <div className="alert alert-error mb-4 animate-fade-in">
            <AlertCircle size={20} />
            <span>{error}</span>
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit}>
          {!isLogin && (
            <div className="input-group animate-fade-in">
              <label className="input-label">Full Name</label>
              <input
                className="input"
                type="text"
                value={fullName}
                onChange={e => setFullName(e.target.value)}
                placeholder="John Doe"
                required={!isLogin}
              />
            </div>
          )}

          <div className="input-group">
            <label className="input-label">Email Address</label>
            <input
              className="input"
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              required
              placeholder="name@example.com"
            />
          </div>

          <div className="input-group">
            <label className="input-label">Password</label>
            <input
              className="input"
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              required
              placeholder="Enter your password"
              minLength={8}
            />
          </div>

          {!isLogin && (
            <div className="input-group animate-fade-in">
              <label className="input-label">Confirm Password</label>
              <input
                className="input"
                type="password"
                value={confirmPassword}
                onChange={e => setConfirmPassword(e.target.value)}
                required
                placeholder="Confirm your password"
              />
            </div>
          )}

          <button
            type="submit"
            className="btn btn-primary btn-full btn-lg mt-4"
            disabled={loading}
          >
            {loading ? (
              <>
                <Loader2 size={20} className="animate-spin" />
                Processing...
              </>
            ) : (
              isLogin ? 'Log In' : 'Create Account'
            )}
          </button>
        </form>

        {/* Footer */}
        <p className="auth-form-footer">
          {isLogin ? (
            <>
              Don't have an account?{' '}
              <button
                type="button"
                className="auth-link"
                onClick={() => switchMode(false)}
              >
                Sign up
              </button>
            </>
          ) : (
            <>
              Already have an account?{' '}
              <button
                type="button"
                className="auth-link"
                onClick={() => switchMode(true)}
              >
                Log in
              </button>
            </>
          )}
        </p>
      </div>
    </div>
  );
}
