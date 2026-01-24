import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

/**
 * RequireAdmin - Protects admin-only routes
 * Redirects to /auth if not logged in, or /app if not admin
 */
export function RequireAdmin({ children }: { children: JSX.Element }) {
    const { user, initializing } = useAuth();
    const location = useLocation();

    // Show loading while checking auth status
    if (initializing) {
        return <div className="auth-loading">ADMIN_AUTH_CHECK_v2...</div>;
    }

    // SECURITY: Log auth state for debugging (remove in production)
    console.log('[RequireAdmin] Auth state:', { user: user?.email, role: user?.role, initializing });

    // Not logged in - redirect to auth
    if (!user) {
        return <Navigate to="/auth" state={{ from: location }} replace />;
    }

    // Not admin - redirect to student app
    if (user.role !== 'admin') {
        return <Navigate to="/app" replace />;
    }

    return children;
}
