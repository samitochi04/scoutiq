import { useEffect, useRef } from "react";
import ScoutiqLogo from '../assets/scoutiq_dark_logo.png';
import "./About.css";

/* ============================================================
   DATA
   ============================================================ */

const FLOW_STEPS = [
  {
    label: "Query Parsed",
    sub: "Intent & entities extracted",
    icon: (
      <svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/></svg>
    ),
  },
  {
    label: "Vector Search",
    sub: "MongoDB Atlas similarity lookup",
    icon: (
      <svg viewBox="0 0 24 24"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5v14c0 1.66 4.03 3 9 3s9-1.34 9-3V5"/><path d="M3 12c0 1.66 4.03 3 9 3s9-1.34 9-3"/></svg>
    ),
  },
  {
    label: "Live Grounding",
    sub: "2026 WC match data injected",
    icon: (
      <svg viewBox="0 0 24 24"><path d="M1 6l5 5-5 5"/><path d="M23 6l-5 5 5 5"/><path d="M16 2l-4 20"/></svg>
    ),
  },
  {
    label: "Reasoning", 
    sub: "Gemini 2.5 Flash multi-step loop",
    icon: (
      <svg viewBox="0 0 24 24"><path d="M12 2a5 5 0 0 1 5 5c0 3-3 6-5 8-2-2-5-5-5-8a5 5 0 0 1 5-5z"/><circle cx="12" cy="7" r="1.5"/></svg>
    ),
  },
  {
    label: "Scout Report",
    sub: "Structured output + confidence score",
    icon: (
      <svg viewBox="0 0 24 24"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>
    ),
  },
];

const USE_CASES = [
  {
    title: "Player Similarity Search",
    body: "Find current players who mirror the style, metrics, and role of any historical reference player.",
    color: "rgba(74,108,247,0.08)",
    iconColor: "#4A6CF7",
    icon: <svg viewBox="0 0 24 24" stroke="#4A6CF7"><circle cx="9" cy="7" r="4"/><path d="M3 21v-2a4 4 0 0 1 4-4h4"/><circle cx="17" cy="17" r="4"/><path d="M13 17h8"/><path d="M17 13v8"/></svg>,
  },
  {
    title: "Form Comparison",
    body: "Stack a player's current tournament stats against any past peak window with a side-by-side breakdown.",
    color: "rgba(16,185,129,0.08)",
    iconColor: "#10B981",
    icon: <svg viewBox="0 0 24 24" stroke="#10B981"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>,
  },
  {
    title: "Transfer Scouting",
    body: "Filter by age, position, pressing metrics, or xG output to surface players available for recruitment.",
    color: "rgba(245,166,35,0.08)",
    iconColor: "#F5A623",
    icon: <svg viewBox="0 0 24 24" stroke="#F5A623"><circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/><line x1="11" y1="8" x2="11" y2="14"/><line x1="8" y1="11" x2="14" y2="11"/></svg>,
  },
  {
    title: "Statistical Deep Dive",
    body: "Query advanced metrics; xG, PPDA, progressive passes, pressures from StatsBomb event-level data.",
    color: "rgba(139,92,246,0.08)",
    iconColor: "#8B5CF6",
    icon: <svg viewBox="0 0 24 24" stroke="#8B5CF6"><line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/></svg>,
  },
  {
    title: "Match Intelligence",
    body: "Ground your queries in live 2026 World Cup match events; goals, lineups, substitutions, and results.",
    color: "rgba(239,68,68,0.08)",
    iconColor: "#EF4444",
    icon: <svg viewBox="0 0 24 24" stroke="#EF4444"><circle cx="12" cy="12" r="10"/><path d="M12 8v4l3 3"/></svg>,
  },
  {
    title: "Historical Archive",
    body: "Reach back into career-spanning records. Explore how a player's role and output evolved over time.",
    color: "rgba(20,184,166,0.08)",
    iconColor: "#14B8A6",
    icon: <svg viewBox="0 0 24 24" stroke="#14B8A6"><path d="M3 3v18h18"/><path d="M7 16l4-4 4 4 4-4"/></svg>,
  },
];

const PERSONAS = [
  {
    title: "Football Enthusiasts",
    body: "Go beyond match highlights. Ask the questions TV pundits never answer with actual data to back up the debate.",
    emoji: "⚽",
    bg: "rgba(74,108,247,0.06)",
  },
  {
    title: "Commentators & Journalists",
    body: "Pull real-time player profiles and comparison narratives mid-broadcast or before deadline.",
    emoji: "🎙️",
    bg: "rgba(245,166,35,0.06)",
  },
  {
    title: "Performance Analysts",
    body: "Run natural-language queries against event-level StatsBomb data without writing a line of SQL.",
    emoji: "📊",
    bg: "rgba(16,185,129,0.06)",
  },
  {
    title: "Scouts & Coaches",
    body: "Shortlist transfer targets with contextual scouting reports grounded in both historical vectors and live tournament form.",
    emoji: "🔭",
    bg: "rgba(139,92,246,0.06)",
  },
];

const TOOLS = [
  {
    name: "Google Agent Builder",
    role: "Agent Orchestration",
    desc: "Manages the multi-step reasoning loop planning sub-queries, routing between tools, and assembling the final scouting report.",
    initials: "G",
    logoBg: "#4285F4",
    logoColor: "#FFFFFF",
  },
  {
    name: "Gemini 2.5 Flash",
    role: "Language Understanding & Generation",
    desc: "Powers intent parsing, structured reasoning over retrieved data, and natural-language report generation with a confidence score.",
    initials: "Gm",
    logoBg: "linear-gradient(135deg, #7B2FBE 0%, #4A6CF7 100%)",
    logoColor: "#FFFFFF",
  },
  {
    name: "MongoDB Atlas + Vector Search",
    role: "Historical Player Embeddings",
    desc: "Stores high-dimensional player style embeddings. Similarity queries retrieve the closest historical matches by playing style, not just name.",
    initials: "M",
    logoBg: "#00684A",
    logoColor: "#FFFFFF",
  },
  {
    name: "StatsBomb Open Data",
    role: "Advanced Event-Level Statistics",
    desc: "Provides granular match events; pressures, progressive carries, xG chains, and set-piece data used to compute player profiles.",
    initials: "SB",
    logoBg: "#0F1923",
    logoColor: "#FFFFFF",
  },
  {
    name: "Wikipedia",
    role: "Biographical & Career Context",
    desc: "Supplies background context on players, tournaments, and historical career timelines to enrich the scouting narrative.",
    initials: "W",
    logoBg: "#3366CC",
    logoColor: "#FFFFFF",
  },
  {
    name: "football-data.org",
    role: "Live Match & Tournament Data",
    desc: "Feeds real-time 2026 World Cup fixtures, results, lineups, and standings to ground the agent in current tournament reality.",
    initials: "fd",
    logoBg: "#1A6B3C",
    logoColor: "#FFFFFF",
  },
];

const COVERAGE_PILLS = [
  "2026 FIFA World Cup",
  "Career historical data",
  "StatsBomb event data",
  "Player similarity vectors",
  "Live match results",
  "Tournament standings",
  "Transfer market context",
  "Head-to-head comparisons",
];

/* ============================================================
   COMPONENT
   ============================================================ */
export default function About({ onNewChat }) {
  const sectionsRef = useRef([]);

  // Intersection observer — triggers reveal animation for below-fold sections
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("visible");
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.07, rootMargin: "0px 0px -32px 0px" }
    );

    sectionsRef.current.forEach((el) => el && observer.observe(el));
    return () => observer.disconnect();
  }, []);

  const addRef = (el) => {
    if (el && !sectionsRef.current.includes(el)) {
      sectionsRef.current.push(el);
    }
  };

  return (
    <>

      <div className="about-page" role="main" aria-label="About ScoutIQ">
        <div className="about-inner">

          {/* ── Hero ───────────────────────────────────────── */}
          <header className="about-hero">
            <img src={ScoutiqLogo} className="logo-icon-about" alt="ScoutIQ Logo" />
            <div className="about-reveal instant" style={{ animationDelay: "0ms" }}>
              <div className="about-hero-badge">
                <span className="about-hero-badge-dot" aria-hidden="true" />
                <span className="about-hero-badge-label">2026 World Cup Edition</span>
              </div>
            </div>
            <div className="about-reveal instant" style={{ animationDelay: "60ms" }}>
              <h1 className="about-hero-title">
                What is <em>ScoutIQ</em>?
              </h1>
            </div>
            <div className="about-reveal instant" style={{ animationDelay: "120ms" }}>
              <p className="about-hero-sub">
                ScoutIQ is a multi-step AI scouting agent that <strong>acts, not just answers</strong>.
                It executes a full reasoning loop, searching historical player vectors, grounding
                itself in live 2026 match data, and returning a structured scouting report
                with a confidence score.
              </p>
            </div>
          </header>

          {/* ── What is ScoutIQ ────────────────────────────── */}
          <section className="about-reveal" ref={addRef} aria-labelledby="about-what-title">
            <div className="about-section-header">
              <div className="about-section-icon-wrap" aria-hidden="true">
                <svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/></svg>
              </div>
              <h2 className="about-section-title" id="about-what-title">What Is ScoutIQ</h2>
            </div>
            <div className="about-card">
              <p>
                ScoutIQ is an <strong>intelligent football analysis platform</strong> built on top of a
                connected stack of AI and data tools. Unlike static dashboards or search engines, ScoutIQ
                understands natural language questions and translates them into multi-step research tasks,
                querying vector databases, fetching live match data, and synthesising everything into a
                readable scouting report.
              </p>
              <p>
                Think of it as having a <strong>football data analyst on call, 24/7</strong>  one who has
                memorised decades of player statistics, watched every 2026 World Cup match, and can answer
                in plain English. Whether you ask about a single player or want a full comparative
                breakdown, ScoutIQ delivers structured intelligence, not a wall of raw numbers.
              </p>
            </div>
          </section>

          {/* ── How It Works ───────────────────────────────── */}
          <section className="about-reveal" ref={addRef} aria-labelledby="about-how-title">
            <div className="about-section-header">
              <div className="about-section-icon-wrap" aria-hidden="true">
                <svg viewBox="0 0 24 24"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>
              </div>
              <h2 className="about-section-title" id="about-how-title">How It Works</h2>
            </div>
            <div className="about-flow-card">
              <div className="about-flow-steps" role="list">
                {FLOW_STEPS.map((step) => (
                  <div className="about-flow-step" role="listitem" key={step.label}>
                    <div className="about-flow-bubble" aria-hidden="true">
                      {step.icon}
                    </div>
                    <p className="about-flow-label">{step.label}</p>
                    <p className="about-flow-sub">{step.sub}</p>
                  </div>
                ))}
              </div>
            </div>
          </section>

          {/* ── What You Can Do ─────────────────────────────── */}
          <section className="about-reveal" ref={addRef} aria-labelledby="about-usecases-title">
            <div className="about-section-header">
              <div className="about-section-icon-wrap" aria-hidden="true">
                <svg viewBox="0 0 24 24"><polyline points="9 11 12 14 22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg>
              </div>
              <h2 className="about-section-title" id="about-usecases-title">What You Can Do</h2>
            </div>
            <div className="about-grid-2" role="list">
              {USE_CASES.map((uc) => (
                <div className="about-grid-card" role="listitem" key={uc.title}>
                  <div
                    className="about-grid-card-icon"
                    style={{ background: uc.color }}
                    aria-hidden="true"
                  >
                    {uc.icon}
                  </div>
                  <p className="about-grid-card-title">{uc.title}</p>
                  <p className="about-grid-card-body">{uc.body}</p>
                </div>
              ))}
            </div>
          </section>

          {/* ── Who Is It For ───────────────────────────────── */}
          <section className="about-reveal" ref={addRef} aria-labelledby="about-who-title">
            <div className="about-section-header">
              <div className="about-section-icon-wrap" aria-hidden="true">
                <svg viewBox="0 0 24 24"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
              </div>
              <h2 className="about-section-title" id="about-who-title">Who Is It For</h2>
            </div>
            <div className="about-grid-2" role="list">
              {PERSONAS.map((p) => (
                <div className="about-grid-card" role="listitem" key={p.title}>
                  <div
                    className="about-grid-card-icon"
                    style={{ background: p.bg, fontSize: "18px" }}
                    aria-hidden="true"
                  >
                    {p.emoji}
                  </div>
                  <p className="about-grid-card-title">{p.title}</p>
                  <p className="about-grid-card-body">{p.body}</p>
                </div>
              ))}
            </div>
          </section>

          {/* ── Powered By ──────────────────────────────────── */}
          <section className="about-reveal" ref={addRef} aria-labelledby="about-tools-title">
            <div className="about-section-header">
              <div className="about-section-icon-wrap" aria-hidden="true">
                <svg viewBox="0 0 24 24"><rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>
              </div>
              <h2 className="about-section-title" id="about-tools-title">Powered By</h2>
            </div>
            <div className="about-grid-2" role="list">
              {TOOLS.map((tool) => (
                <div className="about-tool-card" role="listitem" key={tool.name}>
                  <div
                    className="about-tool-logo"
                    style={{ background: tool.logoBg, color: tool.logoColor }}
                    aria-hidden="true"
                  >
                    {tool.initials}
                  </div>
                  <div className="about-tool-info">
                    <p className="about-tool-name">{tool.name}</p>
                    <p className="about-tool-role">{tool.role}</p>
                    <p className="about-tool-desc">{tool.desc}</p>
                  </div>
                </div>
              ))}
            </div>
          </section>

          {/* ── Data Coverage ───────────────────────────────── */}
          <section className="about-reveal" ref={addRef} aria-labelledby="about-coverage-title">
            <div className="about-section-header">
              <div className="about-section-icon-wrap" aria-hidden="true">
                <svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>
              </div>
              <h2 className="about-section-title" id="about-coverage-title">Data Coverage</h2>
            </div>
            <div className="about-coverage-card">
              <div className="about-card" style={{ padding: 0, border: "none", borderRadius: 0 }}>
                <p>
                  ScoutIQ's knowledge spans <strong>historical career data</strong> for thousands of
                  professional players encoded as vector embeddings, combined with <strong>real-time
                  2026 World Cup match intelligence</strong>. Every response is grounded in at least
                  one live data source, no hallucinated statistics.
                </p>
              </div>
              <div className="about-coverage-pills" role="list" aria-label="Data types covered">
                {COVERAGE_PILLS.map((pill) => (
                  <span className="about-coverage-pill" role="listitem" key={pill}>
                    <span className="about-coverage-pill-dot" aria-hidden="true" />
                    {pill}
                  </span>
                ))}
              </div>
            </div>
          </section>

          {/* ── CTA ─────────────────────────────────────────── */}
          {onNewChat && (
            <section className="about-reveal" ref={addRef}>
              <div className="about-cta-card">
                <div className="about-cta-left">
                  <p className="about-cta-title">Ready to start scouting?</p>
                  <p className="about-cta-sub">Ask your first query, it takes seconds.</p>
                </div>
                <button
                  className="about-cta-btn"
                  onClick={onNewChat}
                  aria-label="Start a new scouting query"
                >
                  Start Scouting
                  <svg viewBox="0 0 24 24" aria-hidden="true">
                    <line x1="5" y1="12" x2="19" y2="12"/>
                    <polyline points="12 5 19 12 12 19"/>
                  </svg>
                </button>
              </div>
            </section>
          )}

          {/* ── Footer note ─────────────────────────────────── */}
          <footer className="about-reveal about-footer" ref={addRef}>
            <strong>ScoutIQ</strong> AI Football Scouting Agent &nbsp;·&nbsp; 2026 World Cup Edition
            <br />
            Built with Google Agent Builder · Gemini 2.5 Flash · MongoDB Atlas
          </footer>

        </div>
      </div>
    </>
  );
}