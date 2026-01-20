import { Terminal, Trash2 } from 'lucide-react';

interface DebugConsoleProps {
  lines: string[];
  onClear: () => void;
}

export default function DebugConsole({ lines, onClear }: DebugConsoleProps) {
  return (
    <div className="debug-console glass-card animate-fade-in-up">
      <div className="debug-console-header">
        <div className="debug-title">
          <Terminal size={18} />
          <h3>Debug Console</h3>
          <span className="badge badge-warning">Admin</span>
        </div>
        {lines.length > 0 && (
          <button
            className="btn btn-ghost btn-sm"
            onClick={onClear}
            type="button"
          >
            <Trash2 size={14} />
            Clear
          </button>
        )}
      </div>

      <pre className="debug-console-output">
        {lines.length === 0
          ? 'Debug logging is enabled. Waiting for OpenAI traffic...'
          : lines.join('\n\n')}
      </pre>
    </div>
  );
}
