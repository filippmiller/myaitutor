import { Calendar, MessageSquare, BookMarked } from 'lucide-react';
import { SessionSummary } from '../../api/progress';

interface RecentLessonsProps {
  sessions: SessionSummary[];
}

function formatDate(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

  if (diffDays === 0) {
    return `Today at ${date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;
  } else if (diffDays === 1) {
    return `Yesterday at ${date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;
  } else if (diffDays < 7) {
    return `${diffDays} days ago`;
  } else {
    return date.toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' });
  }
}

export default function RecentLessons({ sessions }: RecentLessonsProps) {
  if (sessions.length === 0) {
    return (
      <div className="recent-lessons glass-card animate-fade-in-up delay-300">
        <div className="recent-lessons-header">
          <BookMarked size={20} />
          <h3>Recent Lessons</h3>
        </div>
        <div className="recent-lessons-empty">
          <p>No lessons yet. Start your first voice lesson above!</p>
        </div>
      </div>
    );
  }

  return (
    <div className="recent-lessons glass-card animate-fade-in-up delay-300">
      <div className="recent-lessons-header">
        <BookMarked size={20} />
        <h3>Recent Lessons</h3>
      </div>

      <div className="recent-lessons-list">
        {sessions.map((session, index) => (
          <div
            key={session.id}
            className={`lesson-item animate-fade-in-up delay-${(index + 1) * 100}`}
          >
            <div className="lesson-item-date">
              <Calendar size={14} />
              <span>{formatDate(session.created_at)}</span>
            </div>

            {session.summary_text && (
              <p className="lesson-item-summary">{session.summary_text}</p>
            )}

            {session.practiced_words.length > 0 && (
              <div className="lesson-item-words">
                <MessageSquare size={12} />
                <span>Practiced: {session.practiced_words.slice(0, 5).join(', ')}</span>
                {session.practiced_words.length > 5 && (
                  <span className="words-more">+{session.practiced_words.length - 5} more</span>
                )}
              </div>
            )}

            {session.weak_words.length > 0 && (
              <div className="lesson-item-weak">
                <span className="weak-label">Focus on:</span>
                {session.weak_words.slice(0, 3).map((word, i) => (
                  <span key={i} className="badge badge-warning">{word}</span>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
