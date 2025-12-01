import { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { authApi, User, LoginData, RegisterData } from '../api/auth';

interface AuthContextType {
    user: User | null;
    initializing: boolean;
    login: (data: LoginData) => Promise<void>;
    register: (data: RegisterData) => Promise<void>;
    logout: () => Promise<void>;
    refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
    const [user, setUser] = useState<User | null>(null);
    const [initializing, setInitializing] = useState(true);

    const refreshUser = async () => {
        try {
            const currentUser = await authApi.getCurrentUser();
            setUser(currentUser);
        } catch (error) {
            console.error('Failed to fetch user', error);
            setUser(null);
        }
    };

    useEffect(() => {
        const init = async () => {
            await refreshUser();
            setInitializing(false);
        };
        init();
    }, []);

    const login = async (data: LoginData) => {
        const response = await authApi.login(data);
        setUser(response.user);
    };

    const register = async (data: RegisterData) => {
        const response = await authApi.register(data);
        setUser(response.user);
    };

    const logout = async () => {
        await authApi.logout();
        setUser(null);
    };

    return (
        <AuthContext.Provider value={{ user, initializing, login, register, logout, refreshUser }}>
            {children}
        </AuthContext.Provider>
    );
}

export function useAuth() {
    const context = useContext(AuthContext);
    if (context === undefined) {
        throw new Error('useAuth must be used within an AuthProvider');
    }
    return context;
}
