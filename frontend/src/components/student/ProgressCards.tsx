import { BookOpen, Clock, Flame, Sparkles } from 'lucide-react';
import { ProgressState } from '../../api/progress';

interface ProgressCardsProps {
  progress: ProgressState | null;
}

export default function ProgressCards({ progress }: ProgressCardsProps) {
  const cards = [
    {
      icon: BookOpen,
      value: progress?.known_words?.length ?? 0,
      label: 'Words Learned',
      color: 'accent',
    },
    {
      icon: Clock,
      value: progress?.session_count ?? 0,
      label: 'Sessions',
      color: 'success',
    },
    {
      icon: Flame,
      value: calculateStreak(progress?.last_session_at),
      label: 'Day Streak',
      color: 'warning',
    },
    {
      icon: Sparkles,
      value: progress?.xp_points ?? 0,
      label: 'XP Points',
      color: 'primary',
    },
  ];

  return (
    <div className="progress-cards animate-fade-in-up delay-200">
      {cards.map((card, index) => (
        <div
          key={card.label}
          className={`stat-card stat-card-${card.color} animate-scale-in delay-${(index + 1) * 100}`}
        >
          <div className={`stat-card-icon stat-icon-${card.color}`}>
            <card.icon size={22} />
          </div>
          <div className="stat-card-value">{card.value}</div>
          <div className="stat-card-label">{card.label}</div>
        </div>
      ))}
    </div>
  );
}

function calculateStreak(lastSessionAt: string | null | undefined): number {
  if (!lastSessionAt) return 0;

  const lastSession = new Date(lastSessionAt);
  const today = new Date();
  const diffDays = Math.floor((today.getTime() - lastSession.getTime()) / (1000 * 60 * 60 * 24));

  // If last session was today or yesterday, show streak of 1
  // In a real app, this would be calculated from backend
  if (diffDays <= 1) return 1;
  return 0;
}
