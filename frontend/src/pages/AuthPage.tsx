import AuthBranding from '../components/auth/AuthBranding';
import AuthForm from '../components/auth/AuthForm';
import './AuthPage.css';

export default function AuthPage() {
  return (
    <div className="auth-page">
      {/* Left panel - Branding (hidden on mobile) */}
      <div className="auth-panel-left hide-mobile">
        <AuthBranding />
      </div>

      {/* Right panel - Form */}
      <div className="auth-panel-right">
        <AuthForm />
      </div>
    </div>
  );
}
