export type ProgressState = {
    session_count: number;
    total_messages: number;
    last_session_at: string | null;
    xp_points: number;
    weak_words: string[];
    known_words: string[];
};

export type SessionSummary = {
    id: number;
    created_at: string;
    summary_text: string | null;
    practiced_words: string[];
    weak_words: string[];
    grammar_notes: string[];
};

export type ProgressResponse = {
    state: ProgressState;
    recent_sessions: SessionSummary[];
};

export const progressApi = {
    getProgress: async (): Promise<ProgressResponse> => {
        const response = await fetch('/api/progress', {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
            },
        });

        if (!response.ok) {
            throw response; // Throw the response so we can check status
        }

        return response.json();
    }
};
