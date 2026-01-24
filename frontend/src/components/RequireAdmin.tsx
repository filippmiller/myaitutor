import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export function RequireAdmin({ children }: { children: JSX.Element }) {
    const { user, initializing } = useAuth();
    const location = useLocation();

    if (initializing) {
        return <div>Loading...</div>;
    }

    if (!user) {
        return <Navigate to="/auth" state={{ from: location }} replace />;
    }

    if (user.role !== 'admin') {
        return <Navigate to="/app" replace />;
    }

    return children;
}
