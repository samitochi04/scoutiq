import "./LoadingIndicator.css";

export default function LoadingIndicator({ steps = [] }) {
  const lastStep = steps[steps.length - 1];

  return (
    <div className="loading-indicator">
      <div className="scouting-animation">
        <div className="radar-ring r1" />
        <div className="radar-ring r2" />
        <div className="radar-ring r3" />
        <div className="radar-dot" />
      </div>
      <div className="loading-text-area">
        <span className="loading-label">
          Scouting
          <span className="dot-1">.</span>
          <span className="dot-2">.</span>
          <span className="dot-3">.</span>
        </span>
        {lastStep && (
          <span className="loading-step">
            {lastStep.step || lastStep.message || "Querying database..."}
          </span>
        )}
      </div>
    </div>
  );
}

export function ReasoningPanel({ steps }) {
  if (!steps || steps.length === 0) return null;

  return (
    <div className="reasoning-panel">
      <div className="reasoning-header">
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
          <circle cx="12" cy="12" r="10" />
          <polyline points="12 6 12 12 16 14" />
        </svg>
        Agent Reasoning
      </div>
      <div className="reasoning-steps">
        {steps.map((step, i) => (
          <div key={i} className="reasoning-step">
            <div className="step-icon">
              {step.status === "done" ? (
                <svg
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="#22c55e"
                  strokeWidth="2.5"
                  strokeLinecap="round"
                >
                  <polyline points="20 6 9 17 4 12" />
                </svg>
              ) : (
                <div className="step-spinner" />
              )}
            </div>
            <div className="step-content">
              <span className="step-label">{step.step || step.message}</span>
              {/* {step.tool && <span className="step-tool">{step.tool}()</span>} */}
              {step.result_count != null && (
                <span className="step-result">
                  → {step.result_count} results
                </span>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
