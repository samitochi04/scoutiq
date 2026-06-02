from statsbombpy import sb
import pandas as pd
import json

def get_player_stats(match_id):
    events = sb.events(match_id=match_id)
    
    # Filter out system events (no player attached), dropna remove all rows with missing values
    player_events = events.dropna(subset=['player'])
    
    stats = {}
    
    for _, row in player_events.iterrows():
        player = row['player']
        team = row['team']
        
        if player not in stats:
            stats[player] = {
                'player_name': player,
                'team': team,
                'match_id': match_id,
                'goals': 0,
                'shots': 0,
                'shots_on_target': 0,
                'passes': 0,
                'passes_completed': 0,
                'dribbles': 0,
                'dribbles_completed': 0,
                'pressures': 0,
                'tackles': 0,
                'minutes_played': 0
            }
        
        t = row['type']
        
        if t == 'Shot':
            stats[player]['shots'] += 1
            if row.get('shot_outcome') == 'Goal':
                stats[player]['goals'] += 1
            if row.get('shot_outcome') in ['Goal', 'Saved']:
                stats[player]['shots_on_target'] += 1
        
        elif t == 'Pass':
            stats[player]['passes'] += 1
            if pd.isna(row.get('pass_outcome')):  # NaN outcome = completed pass
                stats[player]['passes_completed'] += 1
        
        elif t == 'Dribble':
            stats[player]['dribbles'] += 1
            if row.get('dribble_outcome') == 'Complete':
                stats[player]['dribbles_completed'] += 1
        
        elif t == 'Pressure':
            stats[player]['pressures'] += 1
        
        elif t == 'Tackle':
            stats[player]['tackles'] += 1
    
    # Pass completion rate
    for p in stats:
        s = stats[p]
        s['pass_completion_pct'] = round(
            s['passes_completed'] / s['passes'] * 100, 1
        ) if s['passes'] > 0 else 0
    
    return list(stats.values())


# Run across ALL World Cup matches
def build_dataset():
    all_players = []
    
    matches_2018 = sb.matches(competition_id=43, season_id=3)
    matches_2022 = sb.matches(competition_id=43, season_id=106)
    all_matches = pd.concat([matches_2018, matches_2022])
    
    for _, match in all_matches.iterrows():
        mid = match['match_id']
        season = match['season']
        stage = match['competition_stage']
        print(f"Processing match {mid}...")
        
        try:
            player_stats = get_player_stats(mid)
            for p in player_stats:
                p['season'] = season
                p['competition_stage'] = stage
                p['home_team'] = match['home_team']
                p['away_team'] = match['away_team']
                p['match_date'] = str(match['match_date'])
            all_players.extend(player_stats)
        except Exception as e:
            print(f"  Skipped match {mid}: {e}")
    
    return all_players

players = build_dataset()
print(f"\nTotal player-match records: {len(players)}")

# Save locally before MongoDB insert
with open('players_raw.json', 'w') as f:
    json.dump(players, f, indent=2)

print("Saved to players_raw.json")