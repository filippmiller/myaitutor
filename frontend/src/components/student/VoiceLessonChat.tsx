import { useEffect, useRef } from 'react';
import { MessageCircle, User, Bot } from 'lucide-react';
import { TranscriptMessage } from '../../hooks/useVoiceLesson';

interface VoiceLessonChatProps {
  transcript: TranscriptMessage[];
  isVisible: boolean;
}

function formatMessageText(text: string): JSX.Element[] {
  // Split on sentence-ending punctuation followed by whitespace
  const parts = text.split(/(?<=[\.\!\?])\s+/);
  return parts.map((part, idx) => (
    <span key={idx}>
      {idx > 0 && <><br /><br /></>}
      {part}
    </span>
  ));
}

export default function VoiceLessonChat({ transcript, isVisible }: VoiceLessonChatProps) {
  const chatEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [transcript]);

  if (!isVisible || transcript.length === 0) {
    return null;
  }

  return (
    <div className="voice-chat glass-card animate-fade-in-up">
      <div className="voice-chat-header">
        <MessageCircle size={20} />
        <h3>Conversation</h3>
      </div>

      <div className="voice-chat-messages">
        {transcript.map((msg, index) => (
          <div
            key={index}
            className={`chat-message ${msg.role === 'user' ? 'chat-message-user' : 'chat-message-assistant'} animate-fade-in-up`}
          >
            <div className="chat-message-avatar">
              {msg.role === 'user' ? <User size={16} /> : <Bot size={16} />}
            </div>
            <div className={`chat-bubble ${msg.role === 'user' ? 'chat-bubble-user' : 'chat-bubble-assistant'}`}>
              <div className="chat-bubble-label">
                {msg.role === 'user' ? 'You' : 'Tutor'}
              </div>
              <div className="chat-bubble-text">
                {msg.role === 'assistant' ? formatMessageText(msg.text) : msg.text}
              </div>
            </div>
          </div>
        ))}
        <div ref={chatEndRef} />
      </div>
    </div>
  );
}
