export interface User {
    id: number;
    email: string;
    full_name?: string | null;
    is_active: boolean;
    role: string;
}

export interface AuthResponse {
    user: User;
    access_token: string;
    token_type: string;
}

export interface RegisterData {
    email: string;
    password: string;
    full_name?: string;
}

export interface LoginData {
    email: string;
    password: string;
}

const API_BASE = '/api/auth';

async function handleResponse<T>(response: Response): Promise<T> {
    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || 'An error occurred');
    }
    return response.json();
}

export const authApi = {
    async register(data: RegisterData): Promise<AuthResponse> {
        const response = await fetch(`${API_BASE}/register`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(data),
            credentials: 'include',
        });
        return handleResponse<AuthResponse>(response);
    },

    async login(data: LoginData): Promise<AuthResponse> {
        const response = await fetch(`${API_BASE}/login`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(data),
            credentials: 'include',
        });
        return handleResponse<AuthResponse>(response);
    },

    async logout(): Promise<void> {
        const response = await fetch(`${API_BASE}/logout`, {
            method: 'POST',
            credentials: 'include',
        });
        return handleResponse<void>(response);
    },

    async getCurrentUser(): Promise<User | null> {
        const response = await fetch(`${API_BASE}/me`, {
            method: 'GET',
            credentials: 'include',
        });
        if (response.status === 401) {
            return null;
        }
        return handleResponse<User>(response);
    },
};
