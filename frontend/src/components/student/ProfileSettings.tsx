import { useState } from 'react';
import { ChevronDown, ChevronUp, User, Save, Loader2 } from 'lucide-react';

export interface UserProfile {
  id?: number;
  name: string;
  english_level: string;
  goals: string;
  pains: string;
}

interface ProfileSettingsProps {
  profile: UserProfile;
  onProfileChange: (profile: UserProfile) => void;
  onSave: () => Promise<void>;
}

export default function ProfileSettings({ profile, onProfileChange, onSave }: ProfileSettingsProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  const handleSave = async () => {
    setIsSaving(true);
    try {
      await onSave();
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="profile-settings glass-card animate-fade-in-up delay-400">
      <button
        className="collapsible-header"
        onClick={() => setIsExpanded(!isExpanded)}
        type="button"
      >
        <div className="profile-header-content">
          <User size={20} />
          <h3>Profile Settings</h3>
        </div>
        <div className={`collapsible-icon ${isExpanded ? 'open' : ''}`}>
          {isExpanded ? <ChevronUp size={20} /> : <ChevronDown size={20} />}
        </div>
      </button>

      {isExpanded && (
        <div className="profile-form animate-fade-in">
          <div className="input-group">
            <label className="input-label">Your Name</label>
            <input
              className="input"
              type="text"
              placeholder="How should the tutor call you?"
              value={profile.name}
              onChange={(e) => onProfileChange({ ...profile, name: e.target.value })}
            />
          </div>

          <div className="input-group">
            <label className="input-label">English Level</label>
            <select
              className="select"
              value={profile.english_level}
              onChange={(e) => onProfileChange({ ...profile, english_level: e.target.value })}
            >
              <option value="A1">A1 - Beginner</option>
              <option value="A2">A2 - Elementary</option>
              <option value="B1">B1 - Intermediate</option>
              <option value="B2">B2 - Upper Intermediate</option>
              <option value="C1">C1 - Advanced</option>
            </select>
          </div>

          <div className="input-group">
            <label className="input-label">Learning Goals</label>
            <textarea
              className="textarea"
              placeholder="What do you want to achieve? (e.g., speak fluently, pass IELTS)"
              value={profile.goals}
              onChange={(e) => onProfileChange({ ...profile, goals: e.target.value })}
            />
          </div>

          <div className="input-group">
            <label className="input-label">Current Challenges</label>
            <textarea
              className="textarea"
              placeholder="What's difficult for you? (e.g., speaking anxiety, grammar)"
              value={profile.pains}
              onChange={(e) => onProfileChange({ ...profile, pains: e.target.value })}
            />
          </div>

          <button
            className="btn btn-primary btn-full"
            onClick={handleSave}
            disabled={isSaving}
          >
            {isSaving ? (
              <>
                <Loader2 size={18} className="animate-spin" />
                Saving...
              </>
            ) : (
              <>
                <Save size={18} />
                Save Profile
              </>
            )}
          </button>
        </div>
      )}
    </div>
  );
}
