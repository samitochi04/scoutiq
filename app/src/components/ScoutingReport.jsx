import { useEffect, useRef, useMemo } from "react";
import { marked } from "marked";
import "./ScoutingReport.css";

// Configure marked with safe settings
marked.setOptions({
  breaks: true,
  gfm: true,
});

function ConfidenceBadge({ level }) {
  const map = {
    HIGH: { label: "🟢 HIGH", cls: "high" },
    MEDIUM: { label: "🟡 MEDIUM", cls: "medium" },
    LOW: { label: "🔴 LOW", cls: "low" },
  };
  const info = map[level] || map.MEDIUM;
  return (
    <span
      className={`confidence-badge ${info.cls}`}
      aria-label={`Confidence: ${level}`}
    >
      {info.label}
    </span>
  );
}

export default function ScoutingReport({ report, confidence, isStreaming }) {
  const containerRef = useRef(null);

  const htmlContent = useMemo(() => {
    if (!report) return "";
    return marked.parse(report);
  }, [report]);

  // Auto-scroll to bottom while streaming
  useEffect(() => {
    if (isStreaming && containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [htmlContent, isStreaming]);

  if (!report) return null;

  return (
    <div className="scouting-report-wrapper" ref={containerRef}>
      <div className="scouting-report-header">
        <div className="report-title-row">
          <svg
            className="report-icon"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
            <polyline points="14 2 14 8 20 8" />
            <line x1="16" y1="13" x2="8" y2="13" />
            <line x1="16" y1="17" x2="8" y2="17" />
          </svg>
          <span className="report-title-label">Scouting Report</span>
        </div>
        {confidence && !isStreaming && <ConfidenceBadge level={confidence} />}
        {isStreaming && (
          <span className="streaming-badge">
            <span className="streaming-dot" />
            Generating...
          </span>
        )}
      </div>
      <div
        className={`scouting-report-body${isStreaming ? " streaming" : ""}`}
        dangerouslySetInnerHTML={{ __html: htmlContent }}
        aria-live={isStreaming ? "polite" : "off"}
        aria-atomic="false"
      />
    </div>
  );
}
