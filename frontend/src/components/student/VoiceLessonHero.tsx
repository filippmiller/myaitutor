import { Mic, Pause, Square, Play, Loader2 } from 'lucide-react';
import { ConnectionStatus } from '../../hooks/useVoiceLesson';

interface VoiceLessonHeroProps {
  isRecording: boolean;
  connectionStatus: ConnectionStatus;
  canResume: boolean;
  sttLanguage: 'ru-RU' | 'en-US';
  onLanguageChange: (lang: 'ru-RU' | 'en-US') => void;
  onStart: () => void;
  onPause: () => void;
  onStop: () => void;
}

export default function VoiceLessonHero({
  isRecording,
  connectionStatus,
  canResume,
  sttLanguage,
  onLanguageChange,
  onStart,
  onPause,
  onStop,
}: VoiceLessonHeroProps) {
  const isConnecting = connectionStatus === 'Connecting...';
  const isPaused = connectionStatus === 'Paused' && canResume;

  return (
    <div className="voice-hero glass-card animate-fade-in-up delay-100">
      <div className="voice-hero-header">
        <div className="voice-hero-title-section">
          <h2 className="voice-hero-title">Voice Lesson</h2>
          <p className="voice-hero-subtitle">
            {isRecording
              ? 'Speak naturally - your AI tutor is listening'
              : isPaused
              ? 'Your lesson is paused - resume when ready'
              : 'Start a conversation with your AI English tutor'}
          </p>
        </div>

        <div className="voice-hero-language">
          <label className="input-label">Your native language</label>
          <select
            className="select"
            value={sttLanguage}
            onChange={(e) => onLanguageChange(e.target.value as 'ru-RU' | 'en-US')}
            disabled={isRecording}
          >
            <option value="ru-RU">Russian</option>
            <option value="en-US">English</option>
          </select>
        </div>
      </div>

      <div className="voice-hero-main">
        {!isRecording ? (
          <button
            className={`voice-hero-cta btn ${isPaused ? 'btn-warning' : 'btn-success'} btn-xl`}
            onClick={onStart}
            disabled={isConnecting}
          >
            {isConnecting ? (
              <>
                <Loader2 size={28} className="animate-spin" />
                <span>Connecting...</span>
              </>
            ) : isPaused ? (
              <>
                <Play size={28} />
                <span>Resume Lesson</span>
              </>
            ) : (
              <>
                <Mic size={28} />
                <span>Start Live Lesson</span>
              </>
            )}
          </button>
        ) : (
          <div className="voice-hero-controls">
            <div className="voice-hero-indicator">
              <div className="recording-dot active" />
              <span className="recording-text">Recording...</span>
            </div>

            <div className="voice-hero-buttons">
              <button
                className="btn btn-warning btn-lg"
                onClick={onPause}
              >
                <Pause size={22} />
                <span>Pause</span>
              </button>
              <button
                className="btn btn-danger btn-lg"
                onClick={onStop}
              >
                <Square size={22} />
                <span>End Lesson</span>
              </button>
            </div>
          </div>
        )}
      </div>

      <div className="voice-hero-status">
        <span className={`status-dot status-${connectionStatus.toLowerCase().replace('...', '')}`} />
        <span className="status-text">{connectionStatus}</span>
      </div>
    </div>
  );
}
