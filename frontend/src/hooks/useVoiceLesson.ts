import { useState, useRef, useCallback } from 'react';

export type ConnectionStatus = 'Disconnected' | 'Connecting...' | 'Connected' | 'Paused' | 'Error';

export interface TranscriptMessage {
  role: 'user' | 'assistant';
  text: string;
  final?: boolean;
}

export interface UseVoiceLessonOptions {
  sttLanguage: 'ru-RU' | 'en-US';
  onAuthError?: () => void;
  onDebugEnabled?: (enabled: boolean) => void;
}

export interface UseVoiceLessonReturn {
  // State
  isRecording: boolean;
  connectionStatus: ConnectionStatus;
  transcript: TranscriptMessage[];
  debugLines: string[];
  debugEnabled: boolean;
  lessonSessionId: number | null;

  // Actions
  startLesson: (isResume?: boolean) => Promise<void>;
  pauseLesson: () => void;
  stopLesson: () => void;
  clearTranscript: () => void;
  clearDebugLines: () => void;
}

export function useVoiceLesson(options: UseVoiceLessonOptions): UseVoiceLessonReturn {
  const { sttLanguage, onDebugEnabled } = options;

  // State
  const [isRecording, setIsRecording] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>('Disconnected');
  const [transcript, setTranscript] = useState<TranscriptMessage[]>([]);
  const [debugEnabled, setDebugEnabled] = useState(false);
  const [debugLines, setDebugLines] = useState<string[]>([]);

  // Refs
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const lessonSessionIdRef = useRef<number | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const audioQueueRef = useRef<Blob[]>([]);
  const isPlayingRef = useRef(false);
  const currentSourceRef = useRef<AudioBufferSourceNode | null>(null);

  // Audio queue management
  const stopAudioPlayback = useCallback(() => {
    if (currentSourceRef.current) {
      try {
        currentSourceRef.current.stop();
      } catch (e) {
        // ignore
      }
      currentSourceRef.current = null;
    }
    audioQueueRef.current = [];
    isPlayingRef.current = false;
  }, []);

  const playNextInQueue = useCallback(async () => {
    if (isPlayingRef.current || audioQueueRef.current.length === 0) return;

    isPlayingRef.current = true;
    const blob = audioQueueRef.current.shift();

    if (!blob) {
      isPlayingRef.current = false;
      return;
    }

    if (!audioContextRef.current) {
      audioContextRef.current = new (window.AudioContext || (window as any).webkitAudioContext)();
    }

    try {
      const arrayBuffer = await blob.arrayBuffer();
      const audioBuffer = await audioContextRef.current.decodeAudioData(arrayBuffer);
      const source = audioContextRef.current.createBufferSource();
      source.buffer = audioBuffer;
      source.connect(audioContextRef.current.destination);

      source.onended = () => {
        isPlayingRef.current = false;
        playNextInQueue();
      };

      currentSourceRef.current = source;
      source.start(0);
    } catch (e) {
      console.error('[AUDIO] Playback failed:', e);
      isPlayingRef.current = false;
      playNextInQueue();
    }
  }, []);

  const queueAudio = useCallback((blob: Blob) => {
    audioQueueRef.current.push(blob);
    playNextInQueue();
  }, [playNextInQueue]);

  // Stop media recorder
  const stopMediaRecorder = useCallback(() => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop();
      mediaRecorderRef.current.stream.getTracks().forEach(track => track.stop());
    }
  }, []);

  // Start lesson
  const startLesson = useCallback(async (isResume: boolean = false) => {
    // Reset debug console for new connection (but keep on resume within same lesson)
    if (!isResume) {
      setDebugLines([]);
    }

    try {
      // 1. Get Microphone Access
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

      // 2. Initialize Audio Context
      if (!audioContextRef.current) {
        audioContextRef.current = new (window.AudioContext || (window as any).webkitAudioContext)();
      }

      // 3. Connect WebSocket
      const isDev = window.location.hostname === 'localhost';
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      let wsUrl = isDev
        ? 'ws://localhost:8000/api/ws/voice'
        : `${protocol}//${window.location.host}/api/ws/voice`;

      if (isResume && lessonSessionIdRef.current) {
        const params = new URLSearchParams({
          lesson_session_id: String(lessonSessionIdRef.current),
          resume: '1',
        });
        wsUrl += `?${params.toString()}`;
      }

      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      setConnectionStatus('Connecting...');

      ws.onopen = () => {
        setConnectionStatus('Connected');
        setIsRecording(true);

        // Send config and start event
        ws.send(JSON.stringify({ type: 'config', stt_language: sttLanguage }));
        ws.send(JSON.stringify({ type: 'system_event', event: 'lesson_started' }));

        // 4. Start MediaRecorder
        const mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
        mediaRecorderRef.current = mediaRecorder;

        mediaRecorder.ondataavailable = (e) => {
          if (e.data.size > 0 && ws.readyState === WebSocket.OPEN) {
            ws.send(e.data);
          }
        };

        mediaRecorder.start(250); // Send chunks every 250ms
      };

      ws.onmessage = async (event) => {
        if (event.data instanceof Blob) {
          // Binary message = Audio
          queueAudio(event.data);
        } else {
          // Text message = JSON
          try {
            const msg = JSON.parse(event.data);

            if (msg.type === 'lesson_info') {
              if (typeof msg.lesson_session_id === 'number') {
                lessonSessionIdRef.current = msg.lesson_session_id;
              }
              if (typeof msg.debug_enabled === 'boolean') {
                setDebugEnabled(msg.debug_enabled);
                onDebugEnabled?.(msg.debug_enabled);
              }
            } else if (msg.type === 'transcript') {
              // If user spoke, stop any current AI speech immediately
              if (msg.role === 'user') {
                stopAudioPlayback();
              }

              setTranscript(prev => {
                const last = prev[prev.length - 1];
                // Only merge if this is a streaming fragment (no "final" flag) AND last message was assistant
                if (last && last.role === 'assistant' && msg.role === 'assistant' && !msg.final) {
                  const newPrev = [...prev];
                  newPrev[prev.length - 1] = { ...last, text: last.text + msg.text };
                  return newPrev;
                }
                // Don't add empty final markers to transcript
                if (msg.final && !msg.text) {
                  return prev;
                }
                return [...prev, { role: msg.role, text: msg.text }];
              });
            } else if (msg.type === 'system') {
              if (msg.level === 'error') {
                alert(`Error: ${msg.message}`);
                setConnectionStatus('Error');
              } else if (msg.level === 'info' && msg.message === 'Lesson paused.') {
                setConnectionStatus('Paused');
              }
            } else if (msg.type === 'debug') {
              const line = `[${msg.direction}][${msg.channel}] ${JSON.stringify(msg.payload)}`;
              setDebugLines(prev => [...prev, line]);
            }
          } catch (e) {
            console.error('[WEBSOCKET] Failed to parse message:', event.data);
          }
        }
      };

      ws.onclose = (event) => {
        if (event.code === 1000 && event.reason === 'lesson_paused') {
          setConnectionStatus('Paused');
        } else {
          let statusMsg: ConnectionStatus = 'Disconnected';
          if (event.code !== 1000 && event.code !== 1001 && event.code !== 1005) {
            statusMsg = 'Error';
            if (event.reason) {
              alert(`Connection closed: ${event.reason}`);
            }
          }
          setConnectionStatus(statusMsg);
        }

        setIsRecording(false);
        stopMediaRecorder();
      };

      ws.onerror = () => {
        setConnectionStatus('Error');
      };

    } catch (err) {
      console.error('[ERROR] Failed to start lesson:', err);
      alert('Could not access microphone');
    }
  }, [sttLanguage, queueAudio, stopAudioPlayback, stopMediaRecorder, onDebugEnabled]);

  // Pause lesson
  const pauseLesson = useCallback(() => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'system_event', event: 'lesson_paused' }));
    }
    stopMediaRecorder();
    stopAudioPlayback();
    setIsRecording(false);
  }, [stopMediaRecorder, stopAudioPlayback]);

  // Stop lesson
  const stopLesson = useCallback(() => {
    if (wsRef.current) {
      try {
        wsRef.current.close();
      } catch (e) {
        // ignore
      }
    }
    stopMediaRecorder();
    stopAudioPlayback();
    lessonSessionIdRef.current = null;
    setIsRecording(false);
    setConnectionStatus('Disconnected');
  }, [stopMediaRecorder, stopAudioPlayback]);

  // Clear transcript
  const clearTranscript = useCallback(() => {
    setTranscript([]);
  }, []);

  // Clear debug lines
  const clearDebugLines = useCallback(() => {
    setDebugLines([]);
  }, []);

  return {
    isRecording,
    connectionStatus,
    transcript,
    debugLines,
    debugEnabled,
    lessonSessionId: lessonSessionIdRef.current,

    startLesson,
    pauseLesson,
    stopLesson,
    clearTranscript,
    clearDebugLines,
  };
}
