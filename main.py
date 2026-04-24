#!/usr/bin/env python3
"""
IPL Fantasy Premier League 2026 – Main CLI.

Usage:
    python main.py                       Show leaderboard
    python main.py matches              List recent IPL matches
    python main.py score <match_id>     Calculate scores for a match
    python main.py summary <match_id>   Team summary with all players
    python main.py detail <match_id>    Detailed point breakdown
    python main.py export-summary <match_id>  Export summary to Excel
    python main.py export-detail <match_id>   Export detail to Excel
    python main.py history              Show all processed matches
    python main.py sheet                Show detailed scoring sheet
    python main.py set-captain          Set captain/VC for a team
    python main.py master               Show master scoresheet (all matches)
    python main.py export-master         Export master scoresheet to Excel
    python main.py rebuild-master       Rebuild master scoresheet from history
    python main.py scorecard <match_id>  Show raw cricket scorecard
    python main.py export-scorecard <match_id>  Export scorecard to Excel
    python main.py export-team-points <match_id> Export team points to Excel
    python main.py export-teams            Export all team rosters to Excel
    python main.py export-analytics        Export analytics dashboard to Excel
    python main.py players [team]           Show players database (optional: filter by IPL team)
    python main.py rescore <match_id>    Remove & recalculate scores for a match
    python main.py runserver                Start web server (default: http://localhost:8000)
"""
import os
import sys
from datetime import date

MATCH_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Match data")
os.makedirs(MATCH_DATA_DIR, exist_ok=True)

from cricbuzz_api import get_recent_matches, get_scorecard, get_match_mom
from calculator import calculate_match_scores
from leaderboard import (
    show_leaderboard, show_match_history, show_match_detail,
    show_scoring_sheet, show_summary, show_detailed,
    export_summary_to_excel, export_detailed_to_excel,
    show_master_scoresheet, export_master_to_excel,
    show_scorecard, export_scorecard_to_excel,
    export_team_points_to_excel,
    export_teams_to_excel,
    export_analytics_to_excel,
)
from storage import (
    load_scores, save_scores, is_match_processed, record_match,
    load_teams, save_teams, load_players,
    get_cached_scorecard, cache_scorecard, append_to_scoring_sheet,
    update_master_scoresheet, rebuild_master_scoresheet,
    unprocess_match, remove_match_from_scoring_sheet, remove_match_from_master,
)


def cmd_leaderboard():
    show_leaderboard()


def cmd_matches():
    print("\nFetching recent IPL matches...\n")
    matches = get_recent_matches()
    if not matches:
        print("No IPL matches found. Check if the season has started or API key is set.\n")
        return
    for m in matches:
        state_tag = f"[{m['state']}]" if m["state"] else ""
        print(f"  ID: {m['match_id']}  {m['team1']} vs {m['team2']}  "
              f"{m['description']}  {state_tag}")
        print(f"      {m['status']}")
    print()


def cmd_score(match_id: int):
    if is_match_processed(match_id):
        print(f"\nMatch {match_id} has already been processed. Skipping.\n")
        return

    # Try cached scorecard first, fetch from API only if not cached
    scorecard_data = get_cached_scorecard(match_id)
    if scorecard_data:
        print(f"\nUsing cached scorecard for match {match_id}.")
    else:
        print(f"\nFetching scorecard for match {match_id} from API...")
        scorecard_data = get_scorecard(match_id)
        print("Scorecard fetched.")

    # Fetch Man of the Match if not already in scorecard
    if not scorecard_data.get("man_of_the_match"):
        print("Fetching Man of the Match...")
        mom = get_match_mom(match_id)
        if mom:
            scorecard_data["man_of_the_match"] = mom
            print(f"  MoM: {mom}")
        else:
            print("  MoM: not available from API")

    # Cache the scorecard (with MoM data merged)
    cache_scorecard(match_id, scorecard_data)
    print("Scorecard cached locally.")

    print("Calculating fantasy scores...")
    match_results = calculate_match_scores(scorecard_data)

    # Build description
    desc = f"Match {match_id}"
    header = scorecard_data.get("matchHeader", {})
    if header:
        t1 = header.get("team1", {}).get("shortName", "")
        t2 = header.get("team2", {}).get("shortName", "")
        status = header.get("status", "")
        if t1 and t2:
            desc = f"{t1} vs {t2} – {status}"

    show_match_detail(match_results, desc)

    # Update cumulative scores
    scores = load_scores()
    team_scores_for_record = {}
    for owner, data in match_results.items():
        scores[owner] = round(scores.get(owner, 0) + data["total"], 2)
        team_scores_for_record[owner] = data["total"]

    save_scores(scores)
    record_match(match_id, desc, team_scores_for_record)

    # Save detailed scoring sheet (player-level breakdown + cumulative)
    append_to_scoring_sheet(match_id, desc, match_results, scores)

    # Update master scoresheet
    update_master_scoresheet(match_id, desc, match_results, scores)

    print(f"✓ Match {match_id} scores saved.\n")
    show_leaderboard()

    # Auto-export all 3 Excel files
    today = date.today().strftime("%Y%m%d")
    scorecard_data_for_export = get_cached_scorecard(match_id)
    if scorecard_data_for_export:
        export_scorecard_to_excel(scorecard_data_for_export,
                                  os.path.join(MATCH_DATA_DIR, f"{today}_scorecard_{match_id}.xlsx"), match_id)
    export_team_points_to_excel(match_results, desc,
                                os.path.join(MATCH_DATA_DIR, f"{today}_team_points_{match_id}.xlsx"))
    export_master_to_excel(os.path.join(MATCH_DATA_DIR, f"{today}_master_scoresheet.xlsx"))


def cmd_history():
    show_match_history()


def cmd_sheet():
    show_scoring_sheet()


def _load_match_results(match_id: int) -> tuple[dict, str]:
    """Load scorecard and compute match results. Returns (results, description)."""
    scorecard_data = get_cached_scorecard(match_id)
    if not scorecard_data:
        print(f"\nFetching scorecard for match {match_id} from API...")
        scorecard_data = get_scorecard(match_id)
        cache_scorecard(match_id, scorecard_data)

    match_results = calculate_match_scores(scorecard_data)

    desc = f"Match {match_id}"
    header = scorecard_data.get("matchHeader", {})
    if header:
        t1 = header.get("team1", {}).get("shortName", "")
        t2 = header.get("team2", {}).get("shortName", "")
        status = header.get("status", "")
        if t1 and t2:
            desc = f"{t1} vs {t2} – {status}"
    # Try appindex for description if matchHeader missing
    if desc == f"Match {match_id}":
        appindex = scorecard_data.get("appindex", {})
        seo = appindex.get("seoTitle", "")
        if seo:
            desc = seo.split(" | ")[0].replace("Cricket scorecard - ", "")

    return match_results, desc


def cmd_summary(match_id: int):
    match_results, desc = _load_match_results(match_id)
    show_summary(match_results, desc)


def cmd_detail(match_id: int):
    match_results, desc = _load_match_results(match_id)
    show_detailed(match_results, desc)


def cmd_export_summary(match_id: int):
    """Export summary view to Excel."""
    match_results, desc = _load_match_results(match_id)
    today = date.today().strftime("%Y%m%d")
    filename = os.path.join(MATCH_DATA_DIR, f"{today}_summary_match_{match_id}.xlsx")
    export_summary_to_excel(match_results, filename)


def cmd_export_detail(match_id: int):
    """Export detailed view to Excel."""
    match_results, desc = _load_match_results(match_id)
    today = date.today().strftime("%Y%m%d")
    filename = os.path.join(MATCH_DATA_DIR, f"{today}_detailed_match_{match_id}.xlsx")
    export_detailed_to_excel(match_results, filename)


def cmd_master():
    show_master_scoresheet()


def cmd_rebuild_master():
    print("\nRebuilding master scoresheet from existing data...")
    rebuild_master_scoresheet()
    print("✓ Master scoresheet rebuilt.\n")
    show_master_scoresheet()


def cmd_rescore(match_id: int):
    """Undo a processed match and recalculate it from the cached scorecard."""
    if not is_match_processed(match_id):
        print(f"\nMatch {match_id} hasn't been processed yet. Use 'score {match_id}' instead.\n")
        return

    print(f"\nRescoring match {match_id}...")

    # 1. Subtract old match scores from cumulative totals
    old_team_scores = unprocess_match(match_id)
    scores = load_scores()
    for owner, pts in old_team_scores.items():
        scores[owner] = round(scores.get(owner, 0) - pts, 2)
    save_scores(scores)

    # 2. Remove match from scoring sheet and master
    remove_match_from_scoring_sheet(match_id)
    remove_match_from_master(match_id)

    print("Old scores removed. Recalculating...")

    # 3. Re-process the match (uses cached scorecard, no API call needed)
    cmd_score(match_id)

def cmd_export_master():
    today = date.today().strftime("%Y%m%d")
    filename = os.path.join(MATCH_DATA_DIR, f"{today}_master_scoresheet.xlsx")
    export_master_to_excel(filename)

def cmd_set_captain():
    teams_data = load_teams()
    owners = list(teams_data["teams"].keys())

    print("\nTeams:")
    for i, owner in enumerate(owners, 1):
        team = teams_data["teams"][owner]
        c = team.get("captain") or "Not set"
        vc = team.get("vice_captain") or "Not set"
        print(f"  {i}. {owner}  (C: {c}, VC: {vc})")

    choice = input("\nSelect team number: ").strip()
    if not choice.isdigit() or int(choice) < 1 or int(choice) > len(owners):
        print("Invalid choice.")
        return

    owner = owners[int(choice) - 1]
    team = teams_data["teams"][owner]
    players = team["players"]

    print(f"\nPlayers in {owner}'s team:")
    for i, p in enumerate(players, 1):
        print(f"  {i}. {p['name']} ({p['role']})")

    cap_choice = input("\nSelect captain number: ").strip()
    if cap_choice.isdigit() and 1 <= int(cap_choice) <= len(players):
        team["captain"] = players[int(cap_choice) - 1]["name"]

    vc_choice = input("Select vice-captain number: ").strip()
    if vc_choice.isdigit() and 1 <= int(vc_choice) <= len(players):
        team["vice_captain"] = players[int(vc_choice) - 1]["name"]

    save_teams(teams_data)
    print(f"\n✓ {owner}: Captain = {team['captain']}, VC = {team['vice_captain']}\n")


def cmd_scorecard(match_id: int):
    scorecard_data = get_cached_scorecard(match_id)
    if not scorecard_data:
        print(f"\nNo cached scorecard for match {match_id}. Run 'score {match_id}' first.\n")
        return
    show_scorecard(scorecard_data, match_id)


def cmd_export_scorecard(match_id: int):
    scorecard_data = get_cached_scorecard(match_id)
    if not scorecard_data:
        print(f"\nNo cached scorecard for match {match_id}. Run 'score {match_id}' first.\n")
        return
    today = date.today().strftime("%Y%m%d")
    filename = os.path.join(MATCH_DATA_DIR, f"{today}_scorecard_{match_id}.xlsx")
    export_scorecard_to_excel(scorecard_data, filename, match_id)


def cmd_export_team_points(match_id: int):
    """Export team points for a specific match to Excel."""
    match_results, desc = _load_match_results(match_id)
    today = date.today().strftime("%Y%m%d")
    filename = os.path.join(MATCH_DATA_DIR, f"{today}_team_points_{match_id}.xlsx")
    export_team_points_to_excel(match_results, desc, filename)


def cmd_players(ipl_team_filter: str = None):
    """Show players database, optionally filtered by IPL team."""
    data = load_players()
    players = data.get("players", {})

    if ipl_team_filter:
        filt = ipl_team_filter.upper()
        players = {k: v for k, v in players.items()
                   if v.get("ipl_team_short", "").upper() == filt}
        if not players:
            print(f"No players found for IPL team '{ipl_team_filter}'.")
            return
        print(f"\n{'='*80}")
        print(f"  Players from {list(players.values())[0]['ipl_team']}")
        print(f"{'='*80}")
    else:
        print(f"\n{'='*80}")
        print(f"  Players Database  ({len(players)} players)")
        print(f"{'='*80}")

    # Group by IPL team
    from collections import defaultdict
    by_team = defaultdict(list)
    for p in players.values():
        by_team[p.get('ipl_team_short', 'Unknown')].append(p)

    for team_short in sorted(by_team.keys()):
        team_players = sorted(by_team[team_short], key=lambda x: x['name'])
        full_name = team_players[0]['ipl_team']
        print(f"\n  {full_name} ({team_short}) - {len(team_players)} players")
        print(f"  {'-'*76}")
        print(f"  {'Name':25s} {'Role':15s} {'Country':10s} {'Price':>6s}  Fantasy Owner(s)")
        print(f"  {'-'*76}")
        for p in team_players:
            owners = ', '.join(p.get('fantasy_owners', []))
            print(f"  {p['name']:25s} {p['role']:15s} {p['country']:10s} {p['price']:>6}  {owners}")

    print()


def cmd_runserver():
    """Start the web server."""
    import uvicorn
    from config import HOST, PORT, RELOAD
    
    print("\n" + "="*60)
    print("  IPL Fantasy League 2026 - Web Server")
    print("="*60)
    print("\n  Starting web server...")
    print(f"  URL: http://localhost:{PORT}")
    print("\n  Default login:")
    print("    Username: admin")
    print("    Password: admin123")
    print("\n  IMPORTANT: Change the admin password in production!")
    print("  Press Ctrl+C to stop the server")
    print("="*60 + "\n")
    
    uvicorn.run(
        "app:app",
        host=HOST,
        port=PORT,
        reload=RELOAD,
        log_level="info"
    )


def main():
    args = sys.argv[1:]

    if not args:
        cmd_leaderboard()
    elif args[0] == "matches":
        cmd_matches()
    elif args[0] == "score" and len(args) >= 2:
        cmd_score(int(args[1]))
    elif args[0] == "summary" and len(args) >= 2:
        cmd_summary(int(args[1]))
    elif args[0] == "detail" and len(args) >= 2:
        cmd_detail(int(args[1]))
    elif args[0] == "export-summary" and len(args) >= 2:
        cmd_export_summary(int(args[1]))
    elif args[0] == "export-detail" and len(args) >= 2:
        cmd_export_detail(int(args[1]))
    elif args[0] == "history":
        cmd_history()
    elif args[0] == "sheet":
        cmd_sheet()
    elif args[0] == "set-captain":
        cmd_set_captain()
    elif args[0] == "master":
        cmd_master()
    elif args[0] == "export-master":
        cmd_export_master()
    elif args[0] == "rebuild-master":
        cmd_rebuild_master()
    elif args[0] == "scorecard" and len(args) >= 2:
        cmd_scorecard(int(args[1]))
    elif args[0] == "export-scorecard" and len(args) >= 2:
        cmd_export_scorecard(int(args[1]))
    elif args[0] == "export-team-points" and len(args) >= 2:
        cmd_export_team_points(int(args[1]))
    elif args[0] == "export-teams":
        today = date.today().strftime("%Y%m%d")
        export_teams_to_excel(os.path.join(MATCH_DATA_DIR, f"{today}_teams.xlsx"))
    elif args[0] == "export-analytics":
        today = date.today().strftime("%Y%m%d")
        export_analytics_to_excel(os.path.join(MATCH_DATA_DIR, f"{today}_analytics.xlsx"))
    elif args[0] == "rescore" and len(args) >= 2:
        cmd_rescore(int(args[1]))
    elif args[0] == "players":
        cmd_players(args[1] if len(args) >= 2 else None)
    elif args[0] == "runserver":
        cmd_runserver()
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
