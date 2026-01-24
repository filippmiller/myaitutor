import { BrowserRouter as Router, Routes, Route, Link, useNavigate } from 'react-router-dom';
import { LogOut, User, Settings, BookOpen } from 'lucide-react';
import Admin from './pages/Admin';
import StudentDashboard from './pages/StudentDashboard';
import AuthPage from './pages/AuthPage';
import LandingPage from './pages/LandingPage';
import { AdminTutorPipelines } from './pages/AdminTutorPipelines';
import { AuthProvider, useAuth } from './context/AuthContext';
import { RequireAuth } from './components/RequireAuth';
import { RequireAdmin } from './components/RequireAdmin';
import './App.css';

function NavBar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate('/auth');
  };

  return (
    <nav className="navbar">
      <div className="navbar-brand">
        <Link to="/" className="navbar-logo">
          AIlingva
        </Link>
      </div>

      <div className="navbar-links">
        <Link to="/app" className="navbar-link">
          <BookOpen size={18} />
          <span>Learn</span>
        </Link>
        {user?.role === 'admin' && (
          <>
            <Link to="/admin" className="navbar-link">
              <Settings size={18} />
              <span>Admin</span>
            </Link>
            <Link to="/admin/pipelines" className="navbar-link">
              <span>Pipelines</span>
            </Link>
          </>
        )}
      </div>

      <div className="navbar-user">
        {user ? (
          <>
            <div className="navbar-user-info">
              <User size={18} />
              <span>{user.full_name || user.email}</span>
            </div>
            <button onClick={handleLogout} className="btn btn-ghost btn-sm">
              <LogOut size={16} />
              <span className="hide-mobile">Logout</span>
            </button>
          </>
        ) : (
          <Link to="/auth" className="btn btn-primary btn-sm">
            Log in
          </Link>
        )}
      </div>
    </nav>
  );
}

function App() {
  return (
    <AuthProvider>
      <Router>
        <div className="app">
          <NavBar />
          <main className="app-main">
            <Routes>
              <Route path="/admin" element={
                <RequireAdmin>
                  <Admin />
                </RequireAdmin>
              } />
              <Route path="/admin/pipelines" element={
                <RequireAdmin>
                  <AdminTutorPipelines />
                </RequireAdmin>
              } />
              <Route path="/app" element={
                <RequireAuth>
                  <StudentDashboard />
                </RequireAuth>
              } />
              <Route path="/auth" element={<AuthPage />} />
              <Route path="/" element={<LandingPage />} />
            </Routes>
          </main>
        </div>
      </Router>
    </AuthProvider>
  );
}

export default App;
