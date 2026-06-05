import { useState, useRef, useEffect } from "react";
import ScoutingReport from "./ScoutingReport";
import SimilarPlayers from "./SimilarPlayers";
import LoadingIndicator, { ReasoningPanel } from "./LoadingIndicator";
import "./ChatView.css";

const MODES = [
  "Full Report",
  "Quick Scout",
  "Comparison",
  "Statistical Deep Dive",
];

function Message({ msg, isLatest }) {
  const isUser = msg.role === "user";
  return (
    <div className={`message${isUser ? " user-message" : " agent-message"}`}>
      {isUser ? (
        <div className="user-bubble">
          <span className="user-mode-tag">{msg.mode || "Full Report"}</span>
          {msg.content}
        </div>
      ) : (
        <div className="agent-response">
          <ScoutingReport
            report={msg.report}
            confidence={msg.confidence}
            isStreaming={isLatest && !msg.complete}
          />
          {msg.similar_players && msg.similar_players.length > 0 && (
            <SimilarPlayers players={msg.similar_players} />
          )}
        </div>
      )}
    </div>
  );
}

export default function ChatView({
  messages,
  isLoading,
  streamedReport,
  reasoningSteps,
  similarPlayers,
  confidence,
  error,
  onSend,
  onCancel,
  onNewChat,
}) {
  const [input, setInput] = useState("");
  const [mode, setMode] = useState("Full Report");
  const [showModeDropdown, setShowModeDropdown] = useState(false);
  const messagesEndRef = useRef(null);
  const textareaRef = useRef(null);
  const dropdownRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamedReport, isLoading]);

  // Close dropdown on outside click
  useEffect(() => {
    const handler = (e) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setShowModeDropdown(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const handleSend = () => {
    if (!input.trim() || isLoading) return;
    onSend(input.trim(), mode);
    setInput("");
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="chat-view">
      {/* Top bar */}
      <div className="chat-topbar">
        <div className="chat-topbar-left">
          <button
            className="back-btn"
            onClick={onNewChat}
            aria-label="New scout query"
          >
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <line x1="19" y1="12" x2="5" y2="12" />
              <polyline points="12 19 5 12 12 5" />
            </svg>
          </button>
          <div className="chat-topbar-info">
            <span className="chat-title">Scout Session</span>
            <span className="chat-subtitle">
              {messages.filter((m) => m.role === "user").length} quer
              {messages.filter((m) => m.role === "user").length === 1
                ? "y"
                : "ies"}{" "}
              · 2026 WC
            </span>
          </div>
        </div>
        <div className="chat-topbar-right">
          <button className="new-chat-btn" onClick={onNewChat}>
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
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

      {/* Messages area */}
      <div className="messages-area">
        <div className="messages-inner">
          {messages.map((msg, i) => (
            <Message
              key={msg.id || i}
              msg={msg}
              isLatest={i === messages.length - 1}
            />
          ))}

          {/* Live streaming response */}
          {isLoading && (
            <div className="agent-message">
              <LoadingIndicator steps={reasoningSteps} />
              {reasoningSteps.length > 0 && (
                <div className="chat-layout">
                  <div className="chat-main">
                    {streamedReport && (
                      <ScoutingReport
                        report={streamedReport}
                        confidence={null}
                        isStreaming={true}
                      />
                    )}
                  </div>
                  <div className="chat-sidebar">
                    <ReasoningPanel steps={reasoningSteps} />
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Error */}
          {error && (
            <div className="error-message">
              <svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.5"
                width="16"
                height="16"
              >
                <circle cx="12" cy="12" r="10" />
                <line x1="12" y1="8" x2="12" y2="12" />
                <line x1="12" y1="16" x2="12.01" y2="16" />
              </svg>
              {error}
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Input bar */}
      <div className="chat-input-bar">
        <div className="chat-input-container">
          <textarea
            ref={textareaRef}
            className="chat-textarea"
            placeholder="Ask a follow-up or start a new scouting query…"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            maxLength={1000}
            rows={2}
            disabled={isLoading}
            aria-label="Follow-up query"
          />
          <div className="chat-toolbar">
            <div className="mode-selector-wrapper" ref={dropdownRef}>
              <button
                className="mode-selector"
                onClick={() => setShowModeDropdown((v) => !v)}
                aria-haspopup="listbox"
                aria-expanded={showModeDropdown}
              >
                <span className="mode-selector-label">{mode}</span>
                <svg
                  className="mode-selector-chevron"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="#9090B0"
                  strokeWidth="2"
                >
                  <polyline points="6 9 12 15 18 9" />
                </svg>
              </button>
              {showModeDropdown && (
                <div className="mode-dropdown" role="listbox">
                  {MODES.map((m) => (
                    <button
                      key={m}
                      className={`mode-option${m === mode ? " selected" : ""}`}
                      role="option"
                      aria-selected={m === mode}
                      onClick={() => {
                        setMode(m);
                        setShowModeDropdown(false);
                      }}
                    >
                      {m}
                    </button>
                  ))}
                </div>
              )}
            </div>

            <div className="toolbar-right">
              <span className="char-counter">{input.length}/1000</span>
              {isLoading ? (
                <button
                  className="send-button cancel"
                  onClick={onCancel}
                  aria-label="Cancel generation"
                >
                  <svg
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2.5"
                    strokeLinecap="round"
                  >
                    <line x1="18" y1="6" x2="6" y2="18" />
                    <line x1="6" y1="6" x2="18" y2="18" />
                  </svg>
                </button>
              ) : (
                <button
                  className={`send-button${!input.trim() ? " disabled" : ""}`}
                  onClick={handleSend}
                  disabled={!input.trim() || isLoading}
                  aria-label="Send query"
                >
                  <svg
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <line x1="22" y1="2" x2="11" y2="13" />
                    <polygon points="22 2 15 22 11 13 2 9 22 2" />
                  </svg>
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
