import "./SimilarPlayers.css";

const FLAG_MAP = {
  France: "🇫🇷",
  Brazil: "🇧🇷",
  Argentina: "🇦🇷",
  Spain: "🇪🇸",
  Portugal: "🇵🇹",
  Germany: "🇩🇪",
  England: "🏴󠁧󠁢󠁥󠁮󠁧󠁿",
  Italy: "🇮🇹",
  Belgium: "🇧🇪",
  Netherlands: "🇳🇱",
  Croatia: "🇭🇷",
  Uruguay: "🇺🇾",
  Morocco: "🇲🇦",
  Senegal: "🇸🇳",
  Japan: "🇯🇵",
  "South Korea": "🇰🇷",
  Mexico: "🇲🇽",
  USA: "🇺🇸",
  Canada: "🇨🇦",
  Poland: "🇵🇱",
  Switzerland: "🇨🇭",
  Denmark: "🇩🇰",
  Sweden: "🇸🇪",
};

function getFlag(nationality) {
  return FLAG_MAP[nationality] || "🏳️";
}

function getSimilarityColor(score) {
  if (score >= 0.9) return "#22c55e";
  if (score >= 0.75) return "#f59e0b";
  return "#6b7280";
}

function PlayerCard({ player, rank }) {
  const score = player.score || player.vectorSearchScore || 0;
  const pct = Math.round(score * 100);

  return (
    <div
      className="similar-player-card"
      style={{ animationDelay: `${rank * 60}ms` }}
    >
      <div className="player-card-header">
        <div className="player-rank">#{rank + 1}</div>
        <div className="player-flag">{getFlag(player.nationality)}</div>
      </div>
      <div className="player-card-body">
        <div className="player-name">{player.player_name}</div>
        <div className="player-meta">
          <span className="player-nationality">{player.nationality}</span>
          <span className="player-dot">·</span>
          <span className="player-position">{player.position || "Player"}</span>
        </div>
        {player.tournament_year && (
          <div className="player-year">WC {player.tournament_year}</div>
        )}
      </div>
      <div className="player-card-footer">
        <div className="similarity-bar-track">
          <div
            className="similarity-bar-fill"
            style={{ width: `${pct}%`, background: getSimilarityColor(score) }}
          />
        </div>
        <span
          className="similarity-label"
          style={{ color: getSimilarityColor(score) }}
        >
          {pct}% match
        </span>
      </div>
      {player.goals_per90 != null && (
        <div className="player-stats-row">
          <div className="mini-stat">
            <span className="mini-stat-val">
              {player.goals_per90?.toFixed(2)}
            </span>
            <span className="mini-stat-lbl">G/90</span>
          </div>
          {player.pass_completion_pct != null && (
            <div className="mini-stat">
              <span className="mini-stat-val">
                {Math.round(player.pass_completion_pct)}%
              </span>
              <span className="mini-stat-lbl">Pass%</span>
            </div>
          )}
          {player.dribble_success_pct != null && (
            <div className="mini-stat">
              <span className="mini-stat-val">
                {Math.round(player.dribble_success_pct)}%
              </span>
              <span className="mini-stat-lbl">Drib%</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function SimilarPlayers({ players }) {
  if (!players || players.length === 0) return null;

  return (
    <div className="similar-players-section">
      <div className="similar-players-header">
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
          <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
          <circle cx="9" cy="7" r="4" />
          <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
          <path d="M16 3.13a4 4 0 0 1 0 7.75" />
        </svg>
        Similar Players
        <span className="similar-count">{players.length}</span>
      </div>
      <div className="similar-players-grid">
        {players.slice(0, 5).map((player, i) => (
          <PlayerCard key={player.player_id || i} player={player} rank={i} />
        ))}
      </div>
    </div>
  );
}
