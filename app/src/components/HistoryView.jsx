import "./HistoryView.css";

function timeAgo(ts) {
  const diff = Date.now() - new Date(ts).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

function ConfidenceDot({ level }) {
  const colors = { HIGH: "#22c55e", MEDIUM: "#f59e0b", LOW: "#ef4444" };
  return (
    <span
      className="history-confidence-dot"
      style={{ background: colors[level] || "#9090A8" }}
      title={`Confidence: ${level}`}
    />
  );
}

export default function HistoryView({
  conversations,
  onSelect,
  onDelete,
  onClear,
  onNewChat,
}) {
  if (conversations.length === 0) {
    return (
      <div className="history-view">
        <div className="history-header">
          <h2 className="history-title">Scout Reports</h2>
          <button className="new-chat-btn" onClick={onNewChat}>
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
              width="14"
              height="14"
            >
              <line x1="12" y1="5" x2="12" y2="19" />
              <line x1="5" y1="12" x2="19" y2="12" />
            </svg>
            New Scout
          </button>
        </div>
        <div className="history-empty">
          <div className="history-empty-icon">
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
            >
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
              <polyline points="14 2 14 8 20 8" />
            </svg>
          </div>
          <p>No scouting sessions yet</p>
          <button className="start-btn" onClick={onNewChat}>
            Start your first scout
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="history-view">
      <div className="history-header">
        <div className="history-header-left">
          <h2 className="history-title">Scout Reports</h2>
          <span className="history-count">{conversations.length}</span>
        </div>
        <div className="history-header-right">
          <button className="clear-btn" onClick={onClear}>
            Clear all
          </button>
          <button className="new-chat-btn" onClick={onNewChat}>
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
              width="14"
              height="14"
            >
              <line x1="12" y1="5" x2="12" y2="19" />
              <line x1="5" y1="12" x2="19" y2="12" />
            </svg>
            New Scout
          </button>
        </div>
      </div>

      <div className="history-list">
        {conversations.map((conv, i) => (
          <div
            key={conv.id}
            className="history-item"
            style={{ animationDelay: `${i * 30}ms` }}
          >
            <button
              className="history-item-content"
              onClick={() => onSelect(conv)}
            >
              <div className="history-item-top">
                <span className="history-query">{conv.query}</span>
                {conv.response?.confidence && (
                  <ConfidenceDot level={conv.response.confidence} />
                )}
              </div>
              <div className="history-item-meta">
                <span className="history-time">{timeAgo(conv.timestamp)}</span>
                <span className="history-sep">·</span>
                <span className="history-mode">
                  {conv.mode || "Full Report"}
                </span>
                {conv.response?.reasoning_steps?.length > 0 && (
                  <>
                    <span className="history-sep">·</span>
                    <span className="history-tools">
                      {conv.response.reasoning_steps.length} tools used
                    </span>
                  </>
                )}
              </div>
            </button>
            <button
              className="history-delete-btn"
              onClick={(e) => {
                e.stopPropagation();
                onDelete(conv.id);
              }}
              aria-label="Delete this report"
            >
              <svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
              >
                <polyline points="3 6 5 6 21 6" />
                <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
                <path d="M10 11v6" />
                <path d="M14 11v6" />
              </svg>
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
