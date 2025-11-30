import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export function RequireAuth({ children }: { children: JSX.Element }) {
    const { user, initializing } = useAuth();
    const location = useLocation();

    if (initializing) {
        return <div>Loading...</div>;
    }

    if (!user) {
        // Redirect them to the /auth page, but save the current location they were
        // trying to go to when they were redirected. This allows us to send them
        // along to that page after they login, which is a nicer user experience.
        return <Navigate to="/auth" state={{ from: location }} replace />;
    }

    return children;
}
