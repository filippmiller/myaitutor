import { Flame, Sparkles } from 'lucide-react';

interface WelcomeHeaderProps {
  userName: string;
  streak?: number;
  xpPoints?: number;
}

function getGreeting(): string {
  const hour = new Date().getHours();
  if (hour < 12) return 'Good morning';
  if (hour < 18) return 'Good afternoon';
  return 'Good evening';
}

export default function WelcomeHeader({ userName, streak = 0, xpPoints = 0 }: WelcomeHeaderProps) {
  const displayName = userName || 'Learner';
  const greeting = getGreeting();

  return (
    <div className="welcome-header animate-fade-in-up">
      <div className="welcome-content">
        <h1 className="welcome-title">
          {greeting}, <span className="welcome-name">{displayName}</span>!
        </h1>
        <p className="welcome-subtitle">Ready to practice your English today?</p>
      </div>

      <div className="welcome-badges">
        {streak > 0 && (
          <div className="welcome-badge badge-streak animate-scale-in">
            <Flame size={18} className="badge-icon" />
            <span className="badge-value">{streak}</span>
            <span className="badge-label">day streak</span>
          </div>
        )}
        {xpPoints > 0 && (
          <div className="welcome-badge badge-xp animate-scale-in delay-100">
            <Sparkles size={18} className="badge-icon" />
            <span className="badge-value">{xpPoints}</span>
            <span className="badge-label">XP</span>
          </div>
        )}
      </div>
    </div>
  );
}
