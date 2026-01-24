import { Link } from 'react-router-dom';
import { Mic, Brain, Globe, ArrowRight } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import './LandingPage.css';

const valueProps = [
  {
    icon: Mic,
    title: 'Voice-First Learning',
    description: 'Practice speaking naturally with AI conversations'
  },
  {
    icon: Brain,
    title: 'Adaptive Intelligence',
    description: 'Lessons that evolve with your skill level'
  },
  {
    icon: Globe,
    title: 'Real-World English',
    description: 'Master practical communication skills'
  }
];

export default function LandingPage() {
  const { user } = useAuth();

  return (
    <div className="landing-page">
      {/* Floating orbs */}
      <div className="landing-orb landing-orb-1 animate-float" />
      <div className="landing-orb landing-orb-2 animate-float-reverse" />
      <div className="landing-orb landing-orb-3 animate-float-slow" />

      <div className="landing-content">
        {/* Hero Section */}
        <section className="landing-hero">
          <h1 className="landing-title animate-fade-in-up">
            Master English with <span className="text-gradient">AI-Powered</span> Conversations
          </h1>
          <p className="landing-subtitle animate-fade-in-up delay-200">
            Practice speaking naturally with your personal AI tutor.
            Real conversations, instant feedback, measurable progress.
          </p>

          <div className="landing-cta animate-fade-in-up delay-400">
            {user ? (
              <Link to="/app" className="btn btn-primary btn-lg">
                Go to Dashboard
                <ArrowRight size={20} />
              </Link>
            ) : (
              <>
                <Link to="/auth" className="btn btn-primary btn-lg">
                  Start Learning Free
                  <ArrowRight size={20} />
                </Link>
                <Link to="/auth" className="btn btn-outline btn-lg">
                  Sign In
                </Link>
              </>
            )}
          </div>
        </section>

        {/* Value Props */}
        <section className="landing-features">
          {valueProps.map((prop, index) => (
            <div
              key={prop.title}
              className={`landing-feature animate-fade-in-up delay-${(index + 3) * 200}`}
            >
              <div className="landing-feature-icon">
                <prop.icon size={32} />
              </div>
              <h3>{prop.title}</h3>
              <p>{prop.description}</p>
            </div>
          ))}
        </section>

        {/* Social proof */}
        <section className="landing-social-proof animate-fade-in delay-1000">
          <p>Join thousands of learners improving their English every day</p>
        </section>
      </div>
    </div>
  );
}
