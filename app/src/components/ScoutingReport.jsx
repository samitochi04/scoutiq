import { useEffect, useRef, useMemo, useState } from "react";
import { marked } from "marked";
import { generatePDF } from "../utils/pdfGenerator";
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
  const [isDownloading, setIsDownloading] = useState(false);

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

  const handleDownloadPDF = async () => {
    setIsDownloading(true);
    try {
      await generatePDF(report, confidence);
    } catch (error) {
      console.error("Failed to download PDF:", error);
      alert("Failed to download PDF. Please try again.");
    } finally {
      setIsDownloading(false);
    }
  };

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
        <div className="report-header-right">
          {!isStreaming && (
            <button
              className="download-pdf-btn"
              onClick={handleDownloadPDF}
              disabled={isDownloading}
              aria-label="Download report as PDF"
              title="Download report as PDF"
            >
              <svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
                className="download-icon"
              >
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                <polyline points="7 10 12 15 17 10" />
                <line x1="12" y1="15" x2="12" y2="3" />
              </svg>
              {isDownloading ? "Generating..." : "PDF"}
            </button>
          )}
          {confidence && !isStreaming && <ConfidenceBadge level={confidence} />}
        </div>
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
