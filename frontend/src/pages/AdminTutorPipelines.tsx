import React, { useState, useEffect } from 'react';
import './AdminTutorPipelines.css';


interface Lesson {
    id: number;
    user_id: number;
    lesson_number: number;
    is_first_lesson: boolean;
    placement_level: string | null;
    started_at: string;
    ended_at: string | null;
    turn_count: number;
}

interface Turn {
    id: number;
    turn_index: number;
    pipeline_type: string;
    user_text: string | null;
    tutor_text: string | null;
    created_at: string;
    brain_events_count: number;
}

interface BrainEvent {
    id: number;
    lesson_id: number;
    user_id: number;
    turn_id: number | null;
    pipeline_type: string;
    event_type: string;
    event_payload_json: any;
    created_at: string;
}

interface StudentKnowledge {
    user_id: number;
    level: string;
    lesson_count: number;
    first_lesson_completed: boolean;
    vocabulary_json: {
        weak: any[];
        strong: any[];
        neutral: any[];
    };
    grammar_json: {
        patterns: Record<string, any>;
        mistakes: Record<string, number>;
    };
    topics_json: {
        covered: string[];
        to_practice: string[];
    };
    updated_at: string;
}

interface TerminalEvent {
    timestamp: string;
    event_type: string;
    summary: string;
    full_payload: any;
    user_id: number;
    lesson_id: number;
}

export const AdminTutorPipelines: React.FC = () => {
    const [lessons, setLessons] = useState<Lesson[]>([]);
    const [selectedLesson, setSelectedLesson] = useState<Lesson | null>(null);
    const [turns, setTurns] = useState<Turn[]>([]);
    const [brainEvents, setBrainEvents] = useState<BrainEvent[]>([]);
    const [knowledge, setKnowledge] = useState<StudentKnowledge | null>(null);
    const [terminalEvents, setTerminalEvents] = useState<TerminalEvent[]>([]);
    const [selectedUserId, setSelectedUserId] = useState<number | null>(null);
    const [loading, setLoading] = useState(false);
    const [activeView, setActiveView] = useState<'timeline' | 'brain' | 'terminal' | 'knowledge'>('timeline');
    const [autoRefresh, setAutoRefresh] = useState(false);

    // Load lessons
    const loadLessons = async (userId?: number) => {
        setLoading(true);
        try {
            const params = userId ? `?user_id=${userId}` : '';
            const response = await fetch(`/api/admin/tutor/lessons${params}`);
            const data = await response.json();
            setLessons(data);
        } catch (error) {
            console.error('Failed to load lessons:', error);
        } finally {
            setLoading(false);
        }
    };

    // Load turns for selected lesson
    const loadTurns = async (lessonId: number) => {
        setLoading(true);
        try {
            const response = await fetch(`/api/admin/tutor/lessons/${lessonId}/turns`);
            const data = await response.json();
            setTurns(data);
        } catch (error) {
            console.error('Failed to load turns:', error);
        } finally {
            setLoading(false);
        }
    };

    // Load brain events for selected lesson
    const loadBrainEvents = async (lessonId: number) => {
        setLoading(true);
        try {
            const response = await fetch(`/api/admin/tutor/lessons/${lessonId}/brain-events`);
            const data = await response.json();
            setBrainEvents(data);
        } catch (error) {
            console.error('Failed to load brain events:', error);
        } finally {
            setLoading(false);
        }
    };

    // Load student knowledge
    const loadKnowledge = async (userId: number) => {
        setLoading(true);
        try {
            const response = await fetch(`/api/admin/tutor/users/${userId}/knowledge`);
            const data = await response.json();
            setKnowledge(data);
        } catch (error) {
            console.error('Failed to load knowledge:', error);
            setKnowledge(null);
        } finally {
            setLoading(false);
        }
    };

    // Load terminal feed
    const loadTerminalFeed = async (userId?: number) => {
        try {
            const params = userId ? `?user_id=${userId}` : '';
            const response = await fetch(`/api/admin/tutor/brain-events/terminal-feed${params}`);
            const data = await response.json();
            setTerminalEvents(data.events || []);
        } catch (error) {
            console.error('Failed to load terminal feed:', error);
        }
    };

    // Initial load
    useEffect(() => {
        loadLessons();
        loadTerminalFeed();
    }, []);

    // Auto-refresh terminal
    useEffect(() => {
        if (autoRefresh && activeView === 'terminal') {
            const interval = setInterval(() => {
                loadTerminalFeed(selectedUserId || undefined);
            }, 3000); // Refresh every 3 seconds

            return () => clearInterval(interval);
        }
    }, [autoRefresh, activeView, selectedUserId]);

    // When lesson is selected
    useEffect(() => {
        if (selectedLesson) {
            loadTurns(selectedLesson.id);
            loadBrainEvents(selectedLesson.id);
            if (selectedLesson.user_id) {
                loadKnowledge(selectedLesson.user_id);
            }
        }
    }, [selectedLesson]);

    const formatDateTime = (dateString: string) => {
        const date = new Date(dateString);
        return date.toLocaleString();
    };

    const getEventIcon = (eventType: string) => {
        switch (eventType) {
            case 'WEAK_WORD_ADDED':
                return '⚠️';
            case 'GRAMMAR_PATTERN_UPDATE':
                return '📝';
            case 'RULE_CREATED':
                return '📋';
            case 'PLACEMENT_TEST_COMPLETED':
                return '🎯';
            case 'LESSON_SUMMARY_GENERATED':
                return '📊';
            default:
                return '🔔';
        }
    };

    return (
        <div className="admin-tutor-pipelines">
            <header className="pipelines-header">
                <h1>🧠 Tutor Multi-Pipeline Monitor</h1>
                <p>Track lessons, conversation turns, and brain analysis events</p>
            </header>

            <div className="pipelines-controls">
                <div className="view-tabs">
                    <button
                        className={activeView === 'timeline' ? 'active' : ''}
                        onClick={() => setActiveView('timeline')}
                    >
                        📋 Timeline
                    </button>
                    <button
                        className={activeView === 'brain' ? 'active' : ''}
                        onClick={() => setActiveView('brain')}
                    >
                        🧠 Brain Events
                    </button>
                    <button
                        className={activeView === 'terminal' ? 'active' : ''}
                        onClick={() => setActiveView('terminal')}
                    >
                        💻 Live Terminal
                    </button>
                    <button
                        className={activeView === 'knowledge' ? 'active' : ''}
                        onClick={() => setActiveView('knowledge')}
                    >
                        📚 Knowledge State
                    </button>
                </div>

                {activeView === 'terminal' && (
                    <div className="terminal-controls">
                        <label>
                            <input
                                type="checkbox"
                                checked={autoRefresh}
                                onChange={(e) => setAutoRefresh(e.target.checked)}
                            />
                            Auto-refresh (3s)
                        </label>
                        <button onClick={() => loadTerminalFeed(selectedUserId || undefined)}>
                            🔄 Refresh Now
                        </button>
                    </div>
                )}
            </div>

            <div className="pipelines-content">
                {/* Left sidebar: Lessons list */}
                <aside className="lessons-sidebar">
                    <h3>Recent Lessons</h3>
                    {loading && lessons.length === 0 ? (
                        <p>Loading...</p>
                    ) : (
                        <div className="lessons-list">
                            {lessons.map((lesson) => (
                                <div
                                    key={lesson.id}
                                    className={`lesson-item ${selectedLesson?.id === lesson.id ? 'selected' : ''}`}
                                    onClick={() => {
                                        setSelectedLesson(lesson);
                                        setSelectedUserId(lesson.user_id);
                                    }}
                                >
                                    <div className="lesson-header">
                                        <span className="lesson-number">Lesson #{lesson.lesson_number}</span>
                                        {lesson.is_first_lesson && <span className="badge">First</span>}
                                    </div>
                                    <div className="lesson-meta">
                                        <span>User {lesson.user_id}</span>
                                        {lesson.placement_level && <span>Level: {lesson.placement_level}</span>}
                                    </div>
                                    <div className="lesson-stats">
                                        <span>{lesson.turn_count} turns</span>
                                        <span>{formatDateTime(lesson.started_at).split(',')[0]}</span>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </aside>

                {/* Main content area */}
                <main className="pipelines-main">
                    {!selectedLesson && activeView !== 'terminal' ? (
                        <div className="empty-state">
                            <p>Select a lesson from the sidebar to view details</p>
                        </div>
                    ) : (
                        <>
                            {activeView === 'timeline' && selectedLesson && (
                                <div className="timeline-view">
                                    <h2>Conversation Timeline - Lesson #{selectedLesson.lesson_number}</h2>
                                    <div className="turns-table">
                                        <table>
                                            <thead>
                                                <tr>
                                                    <th>#</th>
                                                    <th>Time</th>
                                                    <th>Speaker</th>
                                                    <th>Text</th>
                                                    <th>Events</th>
                                                </tr>
                                            </thead>
                                            <tbody>
                                                {turns.map((turn) => (
                                                    <React.Fragment key={turn.id}>
                                                        {turn.user_text && (
                                                            <tr className="turn-row user-turn">
                                                                <td>{turn.turn_index}</td>
                                                                <td>{new Date(turn.created_at).toLocaleTimeString()}</td>
                                                                <td>👤 User</td>
                                                                <td>{turn.user_text}</td>
                                                                <td>{turn.brain_events_count > 0 ? `${turn.brain_events_count}` : ''}</td>
                                                            </tr>
                                                        )}
                                                        {turn.tutor_text && (
                                                            <tr className="turn-row tutor-turn">
                                                                <td>{turn.turn_index}</td>
                                                                <td>{new Date(turn.created_at).toLocaleTimeString()}</td>
                                                                <td>🤖 Tutor</td>
                                                                <td>{turn.tutor_text}</td>
                                                                <td></td>
                                                            </tr>
                                                        )}
                                                    </React.Fragment>
                                                ))}
                                            </tbody>
                                        </table>
                                    </div>
                                </div>
                            )}

                            {activeView === 'brain' && selectedLesson && (
                                <div className="brain-events-view">
                                    <h2>Brain Events - Lesson #{selectedLesson.lesson_number}</h2>
                                    <div className="brain-events-list">
                                        {brainEvents.map((event) => (
                                            <div key={event.id} className={`brain-event ${event.event_type.toLowerCase()}`}>
                                                <div className="event-header">
                                                    <span className="event-icon">{getEventIcon(event.event_type)}</span>
                                                    <strong>{event.event_type}</strong>
                                                    <span className="event-time">{new Date(event.created_at).toLocaleTimeString()}</span>
                                                </div>
                                                <div className="event-payload">
                                                    <pre>{JSON.stringify(event.event_payload_json, null, 2)}</pre>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}

                            {activeView === 'terminal' && (
                                <div className="terminal-view">
                                    <h2>💻 Live Rules Terminal</h2>
                                    <div className="terminal-window">
                                        {terminalEvents.length === 0 ? (
                                            <div className="terminal-empty">
                                                <p>No events yet. Start a lesson to see events appear here.</p>
                                            </div>
                                        ) : (
                                            <div className="terminal-output">
                                                {terminalEvents.map((event, index) => (
                                                    <div key={index} className="terminal-line">
                                                        <span className="terminal-timestamp">[{event.timestamp}]</span>
                                                        <span className="terminal-event-type">{event.event_type}:</span>
                                                        <span className="terminal-summary">{event.summary}</span>
                                                    </div>
                                                ))}
                                            </div>
                                        )}
                                    </div>
                                </div>
                            )}

                            {activeView === 'knowledge' && knowledge && (
                                <div className="knowledge-view">
                                    <h2>📚 Student Knowledge - User {knowledge.user_id}</h2>
                                    <div className="knowledge-overview">
                                        <div className="knowledge-stat">
                                            <h4>Level</h4>
                                            <p className="stat-value">{knowledge.level}</p>
                                        </div>
                                        <div className="knowledge-stat">
                                            <h4>Lessons</h4>
                                            <p className="stat-value">{knowledge.lesson_count}</p>
                                        </div>
                                        <div className="knowledge-stat">
                                            <h4>First Completed</h4>
                                            <p className="stat-value">{knowledge.first_lesson_completed ? '✅' : '❌'}</p>
                                        </div>
                                    </div>

                                    <div className="knowledge-sections">
                                        <div className="knowledge-section">
                                            <h3>Vocabulary</h3>
                                            <div className="vocab-lists">
                                                <div className="vocab-category weak">
                                                    <h4>⚠️ Weak Words ({knowledge.vocabulary_json.weak.length})</h4>
                                                    <div className="vocab-items">
                                                        {knowledge.vocabulary_json.weak.slice(0, 10).map((item: any, i: number) => (
                                                            <span key={i} className="vocab-item">
                                                                {typeof item === 'string' ? item : item.word}
                                                                {typeof item === 'object' && item.frequency && ` (${item.frequency}x)`}
                                                            </span>
                                                        ))}
                                                    </div>
                                                </div>
                                                <div className="vocab-category strong">
                                                    <h4>✅ Strong Words ({knowledge.vocabulary_json.strong.length})</h4>
                                                    <div className="vocab-items">
                                                        {knowledge.vocabulary_json.strong.slice(0, 10).map((word: string, i: number) => (
                                                            <span key={i} className="vocab-item">{word}</span>
                                                        ))}
                                                    </div>
                                                </div>
                                            </div>
                                        </div>

                                        <div className="knowledge-section">
                                            <h3>Grammar Patterns</h3>
                                            <div className="grammar-patterns">
                                                {Object.entries(knowledge.grammar_json.patterns).map(([pattern, data]: [string, any]) => (
                                                    <div key={pattern} className="grammar-pattern">
                                                        <h4>{pattern.replace(/_/g, ' ')}</h4>
                                                        <div className="pattern-stats">
                                                            <span>Attempts: {data.attempts || 0}</span>
                                                            <span>Mistakes: {data.mistakes || 0}</span>
                                                            <span>Mastery: {((data.mastery || 0) * 100).toFixed(0)}%</span>
                                                        </div>
                                                        <div className="mastery-bar">
                                                            <div
                                                                className="mastery-fill"
                                                                style={{ width: `${(data.mastery || 0) * 100}%` }}
                                                            ></div>
                                                        </div>
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            )}

                            {activeView === 'knowledge' && !knowledge && selectedLesson && (
                                <div className="empty-state">
                                    <p>No knowledge data available for this user</p>
                                </div>
                            )}
                        </>
                    )}
                </main>
            </div>
        </div>
    );
};
