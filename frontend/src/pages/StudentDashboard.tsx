import { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { useNavigate } from 'react-router-dom';
import { progressApi, ProgressResponse } from '../api/progress';
import { useVoiceLesson } from '../hooks/useVoiceLesson';

import WelcomeHeader from '../components/student/WelcomeHeader';
import VoiceLessonHero from '../components/student/VoiceLessonHero';
import VoiceLessonChat from '../components/student/VoiceLessonChat';
import ProgressCards from '../components/student/ProgressCards';
import RecentLessons from '../components/student/RecentLessons';
import ProfileSettings, { UserProfile } from '../components/student/ProfileSettings';
import DebugConsole from '../components/student/DebugConsole';

import './StudentDashboard.css';

export default function StudentDashboard() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  // Profile state
  const [profile, setProfile] = useState<UserProfile>({
    name: '',
    english_level: 'A1',
    goals: '',
    pains: ''
  });

  // Progress state
  const [progress, setProgress] = useState<ProgressResponse | null>(null);

  // Voice lesson settings
  const [sttLanguage, setSttLanguage] = useState<'ru-RU' | 'en-US'>('ru-RU');

  // Voice lesson hook
  const voiceLesson = useVoiceLesson({
    sttLanguage,
    onAuthError: async () => {
      await logout();
      navigate('/auth');
    },
  });

  // Handle auth errors
  const handleAuthError = async (res: Response) => {
    if (res.status === 401) {
      await logout();
      navigate('/auth');
      return true;
    }
    return false;
  };

  // Load profile and progress on mount
  useEffect(() => {
    // Fetch profile
    fetch('/api/profile')
      .then(async res => {
        if (await handleAuthError(res)) return null;
        return res.json();
      })
      .then(data => {
        if (data) setProfile(data);
      })
      .catch(console.error);

    // Fetch progress
    progressApi.getProgress()
      .then(data => setProgress(data))
      .catch(async err => {
        if (err.status === 401) {
          await logout();
          navigate('/auth');
        }
      });
  }, []);

  // Save profile
  const saveProfile = async () => {
    const params = new URLSearchParams();
    params.append('name', profile.name);
    params.append('english_level', profile.english_level);
    params.append('goals', profile.goals);
    params.append('pains', profile.pains);

    const res = await fetch('/api/profile?' + params.toString(), {
      method: 'POST'
    });

    if (await handleAuthError(res)) return;

    const data = await res.json();
    setProfile(data);
  };

  // Handle start lesson
  const handleStartLesson = () => {
    const isPaused = voiceLesson.connectionStatus === 'Paused' && voiceLesson.lessonSessionId;
    voiceLesson.startLesson(!!isPaused);
  };

  // Get user display name
  const userName = profile.name || user?.full_name || '';

  // Can resume lesson
  const canResume = voiceLesson.connectionStatus === 'Paused' && voiceLesson.lessonSessionId !== null;

  return (
    <div className="dashboard">
      <div className="dashboard-container">
        {/* Welcome Header */}
        <WelcomeHeader
          userName={userName}
          streak={progress?.state.session_count ? 1 : 0}
          xpPoints={progress?.state.xp_points}
        />

        {/* Voice Lesson Hero */}
        <VoiceLessonHero
          isRecording={voiceLesson.isRecording}
          connectionStatus={voiceLesson.connectionStatus}
          canResume={canResume}
          sttLanguage={sttLanguage}
          onLanguageChange={setSttLanguage}
          onStart={handleStartLesson}
          onPause={voiceLesson.pauseLesson}
          onStop={voiceLesson.stopLesson}
        />

        {/* Chat Transcript (visible during/after lesson) */}
        <VoiceLessonChat
          transcript={voiceLesson.transcript}
          isVisible={voiceLesson.transcript.length > 0}
        />

        {/* Progress Cards */}
        <ProgressCards progress={progress?.state || null} />

        {/* Recent Lessons */}
        <RecentLessons sessions={progress?.recent_sessions || []} />

        {/* Profile Settings */}
        <ProfileSettings
          profile={profile}
          onProfileChange={setProfile}
          onSave={saveProfile}
        />

        {/* Debug Console (only visible when enabled by admin) */}
        {voiceLesson.debugEnabled && (
          <DebugConsole
            lines={voiceLesson.debugLines}
            onClear={voiceLesson.clearDebugLines}
          />
        )}
      </div>
    </div>
  );
}
