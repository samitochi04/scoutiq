import "./Sidebar.css";
import ScoutiqLogo from '../assets/scoutiq_logo.png';

const ICONS = {
  logo: <img src={ScoutiqLogo} className="logo-icon" alt="ScoutIQ Logo" />,
  wand: (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M15 4V2m0 2v2m0-2h-2m2 0h2M3 15l9-9 6 6-9 9-6-6zm7-7 2 2" />
    </svg>
  ),
  compare: (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
    </svg>
  ),
  history: (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <polyline points="1 4 1 10 7 10" />
      <path d="M3.51 15a9 9 0 1 0 .49-3.5" />
      <polyline points="12 7 12 12 15 15" />
    </svg>
  ),
};

function SidebarIconTile({ icon, label, active, onClick, badge }) {
  return (
    <button
      className={`sidebar-icon-tile${active ? " active" : ""}`}
      onClick={onClick}
      aria-label={label}
      title={label}
    >
      <span className="sidebar-icon">{ICONS[icon]}</span>
      {badge && (
        <span className="sidebar-badge" aria-hidden="true">
          {badge}
        </span>
      )}
      <span className="sidebar-tooltip">{label}</span>
    </button>
  );
}

export default function Sidebar({ activeView, onNavigate }) {
  return (
    <nav className="sidebar" aria-label="ScoutIQ Navigation">
      {/* App tiles */}
      <div className="sidebar-app-tiles">
        <button
          className="sidebar-app-tile logo-tile"
          aria-label="ScoutIQ Home"
          onClick={() => onNavigate("home")}
        >
          <span className="sidebar-icon">{ICONS.logo}</span>
        </button>
      </div>

      {/* Nav group */}
      <div
        className="sidebar-nav-group"
        role="group"
        aria-label="Main navigation"
      >
        <SidebarIconTile
          icon="wand"
          label="New Scout"
          active={activeView === "home"}
          onClick={() => onNavigate("home")}
        />
        <SidebarIconTile
          icon="compare"
          label="Compare"
          onClick={() => onNavigate("home")}
        />
        <SidebarIconTile
          icon="history"
          label="History"
          onClick={() => onNavigate("history")}
        />
      </div>

      {/* Bottom utils */}
      <div className="sidebar-bottom">
        <div className="sidebar-credit">
          <span className="credit-label">World</span>
          <span className="credit-label">Cup</span>
          <span className="credit-label">2026</span>
        </div>
      </div>
    </nav>
  );
}
