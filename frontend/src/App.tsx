import { BrowserRouter as Router, Routes, Route, Link, useNavigate } from 'react-router-dom';
import Admin from './pages/Admin';
import Student from './pages/Student';
import AuthPage from './pages/AuthPage';
import { AuthProvider, useAuth } from './context/AuthContext';
import { RequireAuth } from './components/RequireAuth';

function NavBar() {
    const { user, logout } = useAuth();
    const navigate = useNavigate();

    const handleLogout = async () => {
        await logout();
        navigate('/auth');
    };

    return (
        <nav style={{ padding: '1rem', borderBottom: '1px solid #444', marginBottom: '2rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
                <Link to="/app" style={{ marginRight: '1rem' }}>Student App</Link>
                <Link to="/admin">Admin</Link>
            </div>
            <div>
                {user ? (
                    <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
                        <span>Logged in as {user.full_name || user.email}</span>
                        <button onClick={handleLogout} style={{ padding: '0.4em 0.8em', fontSize: '0.9em' }}>Logout</button>
                    </div>
                ) : (
                    <Link to="/auth">Log in / Sign up</Link>
                )}
            </div>
        </nav>
    );
}

function App() {
    return (
        <AuthProvider>
            <Router>
                <div>
                    <NavBar />
                    <Routes>
                        <Route path="/admin" element={<Admin />} />
                        <Route path="/app" element={
                            <RequireAuth>
                                <Student />
                            </RequireAuth>
                        } />
                        <Route path="/auth" element={<AuthPage />} />
                        <Route path="/" element={
                            <RequireAuth>
                                <Student />
                            </RequireAuth>
                        } />
                    </Routes>
                </div>
            </Router>
        </AuthProvider>
    );
}

export default App;
