"""
Smoke tests for mcp_server/server.py tools.
Run: python mcp_server/test_server.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

import importlib.util

spec = importlib.util.spec_from_file_location("server", ROOT / "mcp_server" / "server.py")
mod  = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

SEP = "-" * 60


def test_get_player_profile():
    print(SEP)
    print("Tool 2: get_player_profile(Mbappe, 2022)")
    r = mod.get_player_profile("Mbappe", 2022)
    master = r["master"]
    profiles = r["tournament_profiles"]
    print(f"  master found: {bool(master)}")
    if master:
        print(f"  player_id={master.get('player_id')}")
        print(f"  active_at_2026_wc={master.get('active_at_2026_wc')}")
        print(f"  career_wc_goals={master.get('career_wc_goals')}")
    print(f"  profiles found: {len(profiles)}")
    for p in profiles:
        print(f"    {p.get('player_name')} | {p.get('tournament_year')} | goals={p.get('goals')} | gp90={p.get('goals_per90')}")
    assert profiles, "Expected at least 1 profile for Mbappe 2022"
    print("  PASS")


def test_get_team_players():
    print(SEP)
    print("Tool 4: get_team_players(France, 2022, Forward)")
    r = mod.get_team_players("France", tournament_year=2022, position="Forward")
    print(f"  {len(r)} forwards found")
    for p in r[:3]:
        print(f"    {p.get('player_name')} | goals={p.get('goals')} | g/90={p.get('goals_per90')}")
    assert len(r) > 0, "Expected France 2022 forwards"
    print("  PASS")


def test_get_team_players_2026_squad():
    print(SEP)
    print("Tool 4: get_team_players(France, active_2026_only=True)")
    r = mod.get_team_players("France", active_2026_only=True)
    print(f"  {len(r)} active 2026 France players")
    for p in r[:3]:
        print(f"    {p.get('player_name')} | positions={p.get('positions_list')}")
    assert len(r) > 0, "Expected France 2026 squad members"
    print("  PASS")


def test_get_match_timeline():
    print(SEP)
    print("Tool 3: get_match_timeline(Mbappe, 2022)")
    r = mod.get_match_timeline("Mbappe", 2022)
    print(f"  {len(r)} match records found")
    for m in r[:3]:
        print(f"    {m.get('match_date')} | {m.get('competition_stage')} | goals={m.get('goals')} | min={m.get('minutes_played')}")
    assert len(r) > 0, "Expected match stats for Mbappe 2022"
    print("  PASS")


def test_search_players():
    print(SEP)
    print("Tool 1: search_players(deep playmaker high pass completion, 2022)")
    r = mod.search_players(
        "deep playmaker, excellent vision, high pass completion",
        tournament_year=2022,
        limit=5,
    )
    print(f"  {len(r)} results")
    for p in r:
        print(f"    {p.get('player_name')} | {p.get('nationality')} | {p.get('position')} | score={p.get('score', 0):.3f}")
    assert len(r) > 0, "Expected vector search results"
    print("  PASS")


def test_resolve_position():
    print(SEP)
    print("Tool 5: resolve_player_position(Zinedine Zidane)")
    r = mod.resolve_player_position("Zinedine Zidane", nationality="France")
    print(f"  position={r.get('position')} | source={r.get('source')} | confidence={r.get('confidence')}")
    print("  PASS (no assertion — source may vary)")


if __name__ == "__main__":
    tests = [
        test_get_player_profile,
        test_get_team_players,
        test_get_team_players_2026_squad,
        test_get_match_timeline,
        test_search_players,
        test_resolve_position,
    ]
    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            print(f"  FAIL: {e}")
            failed += 1

    print(SEP)
    print(f"Results: {passed} passed, {failed} failed")
