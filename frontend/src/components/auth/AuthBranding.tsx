import { Mic, Brain, Globe } from 'lucide-react';

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

export default function AuthBranding() {
  return (
    <div className="auth-branding">
      {/* Floating orbs */}
      <div className="auth-orb auth-orb-1 animate-float" />
      <div className="auth-orb auth-orb-2 animate-float-reverse" />
      <div className="auth-orb auth-orb-3 animate-float-slow" />

      <div className="auth-branding-content">
        <div className="auth-brand-header animate-fade-in-up">
          <h1 className="auth-brand-logo">AIlingva</h1>
          <p className="auth-brand-tagline">
            The future of English learning is here
          </p>
        </div>

        <div className="auth-value-props">
          {valueProps.map((prop, index) => (
            <div
              key={prop.title}
              className={`auth-value-prop animate-fade-in-up delay-${(index + 1) * 200}`}
            >
              <div className="auth-value-icon">
                <prop.icon size={24} />
              </div>
              <div className="auth-value-text">
                <h3>{prop.title}</h3>
                <p>{prop.description}</p>
              </div>
            </div>
          ))}
        </div>

        <div className="auth-brand-footer animate-fade-in delay-800">
          <p>Join thousands of learners worldwide</p>
        </div>
      </div>
    </div>
  );
}
