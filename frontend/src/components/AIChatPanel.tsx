import { useState, useEffect, useRef } from 'react';

interface Message {
    sender: 'human' | 'ai';
    content: string;
    created_at?: string;
}

interface AIChatPanelProps {
    onClose: () => void;
}

export default function AIChatPanel({ onClose }: AIChatPanelProps) {
    const [messages, setMessages] = useState<Message[]>([]);
    const [inputText, setInputText] = useState('');
    const [loading, setLoading] = useState(false);
    const [conversationId, setConversationId] = useState<number | null>(null);
    const messagesEndRef = useRef<HTMLDivElement>(null);

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    };

    useEffect(() => {
        scrollToBottom();
    }, [messages]);

    const sendMessage = async () => {
        if (!inputText.trim() || loading) return;

        const userMessage: Message = {
            sender: 'human',
            content: inputText
        };

        setMessages(prev => [...prev, userMessage]);
        setInputText('');
        setLoading(true);

        try {
            const res = await fetch('/api/admin/ai/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    conversation_id: conversationId,
                    message: inputText
                })
            });

            const data = await res.json();

            if (data.error) {
                const errorMessage: Message = {
                    sender: 'ai',
                    content: `Error: ${data.error}`
                };
                setMessages(prev => [...prev, errorMessage]);
            } else {
                setConversationId(data.conversation_id);

                const aiMessage: Message = {
                    sender: 'ai',
                    content: data.ai_response
                };
                setMessages(prev => [...prev, aiMessage]);

                // If there were actions taken, add a summary
                if (data.actions_taken && data.actions_taken.length > 0) {
                    const actionsSummary = data.actions_taken.map((action: any) => {
                        return `${action.tool}: ${JSON.stringify(action.result)}`;
                    }).join('\n');

                    const actionsMessage: Message = {
                        sender: 'ai',
                        content: `\n**Actions taken:**\n${actionsSummary}`
                    };
                    setMessages(prev => [...prev, actionsMessage]);
                }
            }
        } catch (e) {
            const errorMessage: Message = {
                sender: 'ai',
                content: `Failed to send message: ${e}`
            };
            setMessages(prev => [...prev, errorMessage]);
        } finally {
            setLoading(false);
        }
    };

    const handleKeyPress = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    };

    return (
        <div style={{
            position: 'fixed',
            top: 0,
            right: 0,
            width: '450px',
            height: '100vh',
            background: '#1a1a1a',
            boxShadow: '-4px 0 16px rgba(0,0,0,0.5)',
            display: 'flex',
            flexDirection: 'column',
            zIndex: 1001,
            animation: 'slideIn 0.3s ease-out'
        }}>
            {/* Header */}
            <div style={{
                padding: '1.5rem',
                borderBottom: '1px solid #444',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)'
            }}>
                <div>
                    <h3 style={{ margin: 0, color: 'white' }}>🤖 AI Admin Assistant</h3>
                    <small style={{ color: '#eee', fontSize: '0.85em' }}>Manage tutor rules via natural language</small>
                </div>
                <button
                    onClick={onClose}
                    style={{
                        background: 'rgba(255,255,255,0.2)',
                        border: 'none',
                        color: 'white',
                        width: '32px',
                        height: '32px',
                        borderRadius: '50%',
                        cursor: 'pointer',
                        fontSize: '1.2em',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center'
                    }}
                >
                    ×
                </button>
            </div>

            {/* Messages Area */}
            <div style={{
                flex: 1,
                overflowY: 'auto',
                padding: '1rem',
                display: 'flex',
                flexDirection: 'column',
                gap: '1rem'
            }}>
                {messages.length === 0 && (
                    <div style={{
                        textAlign: 'center',
                        color: '#888',
                        marginTop: '3rem',
                        padding: '0 2rem'
                    }}>
                        <p style={{ fontSize: '1.1em', marginBottom: '0.5rem' }}>👋 Hello!</p>
                        <p style={{ fontSize: '0.9em', lineHeight: '1.5' }}>
                            I can help you manage tutor behavior rules. Try asking me to:
                        </p>
                        <ul style={{ textAlign: 'left', fontSize: '0.85em', lineHeight: '1.8', color: '#aaa' }}>
                            <li>"Create a global greeting rule"</li>
                            <li>"List all active rules"</li>
                            <li>"Show today's session count"</li>
                        </ul>
                    </div>
                )}

                {messages.map((msg, idx) => (
                    <div key={idx} style={{
                        alignSelf: msg.sender === 'human' ? 'flex-end' : 'flex-start',
                        maxWidth: '80%'
                    }}>
                        <div style={{
                            background: msg.sender === 'human' ? '#667eea' : '#2a2a2a',
                            color: 'white',
                            padding: '0.75rem 1rem',
                            borderRadius: msg.sender === 'human' ? '16px 16px 4px 16px' : '16px 16px 16px 4px',
                            fontSize: '0.9em',
                            lineHeight: '1.5',
                            whiteSpace: 'pre-wrap',
                            wordWrap: 'break-word'
                        }}>
                            {msg.content}
                        </div>
                        {msg.created_at && (
                            <small style={{ color: '#666', fontSize: '0.75em', marginTop: '0.25rem', display: 'block' }}>
                                {new Date(msg.created_at).toLocaleTimeString()}
                            </small>
                        )}
                    </div>
                ))}

                {loading && (
                    <div style={{
                        alignSelf: 'flex-start',
                        background: '#2a2a2a',
                        color: '#888',
                        padding: '0.75rem 1rem',
                        borderRadius: '16px 16px 16px 4px',
                        fontSize: '0.9em'
                    }}>
                        Thinking...
                    </div>
                )}

                <div ref={messagesEndRef} />
            </div>

            {/* Input Area */}
            <div style={{
                padding: '1rem',
                borderTop: '1px solid #444',
                background: '#151515'
            }}>
                <div style={{ display: 'flex', gap: '0.5rem' }}>
                    <textarea
                        value={inputText}
                        onChange={e => setInputText(e.target.value)}
                        onKeyPress={handleKeyPress}
                        placeholder="Ask me to create rules, get analytics..."
                        style={{
                            flex: 1,
                            padding: '0.75rem',
                            borderRadius: '8px',
                            border: '1px solid #444',
                            background: '#1a1a1a',
                            color: 'white',
                            fontSize: '0.9em',
                            resize: 'none',
                            minHeight: '60px',
                            fontFamily: 'inherit'
                        }}
                        disabled={loading}
                    />
                    <button
                        onClick={sendMessage}
                        disabled={loading || !inputText.trim()}
                        style={{
                            padding: '0.75rem 1.5rem',
                            borderRadius: '8px',
                            border: 'none',
                            background: loading || !inputText.trim() ? '#444' : 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                            color: 'white',
                            cursor: loading || !inputText.trim() ? 'not-allowed' : 'pointer',
                            fontSize: '0.9em',
                            fontWeight: 'bold',
                            alignSelf: 'flex-end'
                        }}
                    >
                        Send
                    </button>
                </div>
                <small style={{ color: '#666', fontSize: '0.75em', marginTop: '0.5rem', display: 'block' }}>
                    Press Enter to send, Shift+Enter for new line
                </small>
            </div>

            <style>{`
                @keyframes slideIn {
                    from {
                        transform: translateX(100%);
                    }
                    to {
                        transform: translateX(0);
                    }
                }
            `}</style>
        </div>
    );
}
