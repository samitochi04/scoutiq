import { useState, useRef, useEffect } from "react";
import "./QueryHome.css";

const PROMPT_CARDS = [
  {
    text: "What are Messi's statistics in the World Cup 2022?",
    icon: (
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="#C0C0D4"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
        <circle cx="12" cy="7" r="4" />
      </svg>
    ),
  },
  {
    text: "Compare Mbappé's 2022 form to his 2018 peak",
    icon: (
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="#C0C0D4"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
      </svg>
    ),
  },
  {
    text: "Find the best young midfielders in 2026",
    icon: (
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="#C0C0D4"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <circle cx="12" cy="12" r="10" />
        <circle cx="12" cy="12" r="4" />
        <line x1="4.93" y1="4.93" x2="9.17" y2="9.17" />
        <line x1="14.83" y1="14.83" x2="19.07" y2="19.07" />
        <line x1="14.83" y1="9.17" x2="19.07" y2="4.93" />
        <line x1="4.93" y1="19.07" x2="9.17" y2="14.83" />
      </svg>
    ),
  },
  {
    text: "Waht is France's lineup for 2026",
    icon: (
      <svg
        viewBox="0 0 24 24"
        fill="none"
        stroke="#C0C0D4"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <line x1="18" y1="20" x2="18" y2="10" />
        <line x1="12" y1="20" x2="12" y2="4" />
        <line x1="6" y1="20" x2="6" y2="14" />
      </svg>
    ),
  },
];

const MODES = [
  "Full Report",
  "Quick Scout",
  "Comparison",
  "Statistical Deep Dive",
];

export default function QueryHome({ onSubmit }) {
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState("Full Report");
  const [showModeDropdown, setShowModeDropdown] = useState(false);
  const [flashCard, setFlashCard] = useState(null);
  const textareaRef = useRef(null);
  const dropdownRef = useRef(null);

  useEffect(() => {
    // Auto-focus textarea
    const timer = setTimeout(() => textareaRef.current?.focus(), 400);
    return () => clearTimeout(timer);
  }, []);

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

  const handleCardClick = (card, idx) => {
    setFlashCard(idx);
    setQuery(card.text);
    textareaRef.current?.focus();
    setTimeout(() => setFlashCard(null), 300);
  };

  const handleSubmit = () => {
    if (!query.trim()) return;
    onSubmit(query.trim(), mode);
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="query-home">
      <div className="content-column">
        {/* Greeting */}
        <div className="greeting-block">
          <h1 className="greeting-line">
            Hi there, <span className="greeting-name">scout</span>
          </h1>
          <h2 className="greeting-cta">Who are you scouting today?</h2>
          <p className="greeting-subtitle">
            Use one of the common queries below or describe your own to begin
          </p>
        </div>

        {/* Prompt Cards */}
        <div
          className="prompt-card-row"
          role="group"
          aria-label="Quick-start scouting prompts"
        >
          {PROMPT_CARDS.map((card, idx) => (
            <button
              key={idx}
              className={`prompt-card${flashCard === idx ? " flash" : ""}`}
              onClick={() => handleCardClick(card, idx)}
              aria-label={`Use prompt: ${card.text}`}
            >
              <span className="prompt-card-text">{card.text}</span>
              <span className="prompt-card-icon" aria-hidden="true">
                {card.icon}
              </span>
            </button>
          ))}
        </div>

        {/* Query Input */}
        <div className="query-input-container" role="search">
          {/* Live data chip */}
          <button
            className="data-source-chip"
            aria-label="Data source: Live 2026 data"
          >
            <svg
              className="data-source-chip-icon"
              viewBox="0 0 24 24"
              fill="none"
              stroke="#7070A0"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M22 12c0 5.52-4.48 10-10 10S2 17.52 2 12 6.48 2 12 2s10 4.48 10 10z" />
              <path d="M12 8v4l3 3" />
            </svg>
            <span className="data-source-chip-label">⊕ Live Data</span>
          </button>

          <textarea
            ref={textareaRef}
            className="query-textarea"
            placeholder="Ask about any player, match, or comparison…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            maxLength={1000}
            rows={3}
            aria-label="Scout query input"
            aria-describedby="char-counter mode-label"
          />

          <div className="query-toolbar">
            {/* Mode selector */}
            <div className="mode-selector-wrapper" ref={dropdownRef}>
              <button
                id="mode-label"
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
                <div
                  className="mode-dropdown"
                  role="listbox"
                  aria-label="Report mode"
                >
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
              <span
                id="char-counter"
                className="char-counter"
                aria-live="polite"
              >
                {query.length}/1000
              </span>
              <button
                className={`send-button${!query.trim() ? " disabled" : ""}`}
                onClick={handleSubmit}
                disabled={!query.trim()}
                aria-label="Submit scouting query"
                aria-disabled={!query.trim()}
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
            </div>
          </div>
        </div>

        <p className="query-hint">
          Press <kbd>⌘</kbd> + <kbd>Enter</kbd> to send
        </p>
      </div>
    </div>
  );
}
