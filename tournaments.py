"""Tournament registry.

Every tournament (one season of one competition, e.g. IPL 2027 or WPL 2027)
lives in its own folder:

    data/tournaments/<id>/
        tournament.json          settings (name, status, scoring preset, series)
        teams_data.json          fantasy teams (owner -> players, C/VC, budget)
        players_data.json        player database for this tournament
        cumulative_scores.json   created by scoring
        match_history.json       created by scoring
        scoring_sheet.json       created by scoring
        master_scoresheet.json   created by scoring
        scorecards/<match_id>.json

Adding a new tournament = adding a folder with a tournament.json. No code change.
"""
import json
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional

DATA_ROOT = os.environ.get("DATA_ROOT", "data")
TOURNAMENTS_DIR = os.path.join(DATA_ROOT, "tournaments")

# Used when code calls storage/scoring functions without a tournament (CLI).
# Override with:  python main.py --t <id> <command>
DEFAULT_TOURNAMENT_ID = os.environ.get("DEFAULT_TOURNAMENT", "ipl-2026")

STATUS_ORDER = {"live": 0, "auction": 1, "upcoming": 2, "completed": 3}
STATUS_LABELS = {
    "live": "Live now",
    "auction": "Auction",
    "upcoming": "Upcoming",
    "completed": "Past seasons",
}

# Old single-league URLs and ?league= keys, kept so existing links keep working.
LEGACY_KEYS = {"ipl": "ipl-2026", "wwc": "wwc-2026"}
LEGACY_PREFIXES = {"/dashboard": "/ipl/2026", "/wwc": "/wwc/2026"}


@dataclass
class Tournament:
    id: str                      # "ipl-2027" (also the folder name)
    competition: str             # "ipl", "wpl", "wwc" (first URL segment)
    season: str                  # "2027" (second URL segment)
    name: str                    # "IPL Fantasy League 2027"
    emoji: str = "🏏"
    status: str = "upcoming"     # upcoming | auction | live | completed
    scoring_preset: str = "ipl"  # key into scoring.SCORING_PRESETS
    series_keywords: List[str] = field(default_factory=list)  # Cricbuzz series name match
    series_year: str = ""        # must also appear in the series name
    series_exclude: List[str] = field(default_factory=list)
    start_date: str = ""
    end_date: str = ""
    config_source: str = "git"   # "git": teams/players re-synced from repo on deploy
    sort_order: int = 0

    # ── Derived paths (kept as attributes so existing code works unchanged) ──
    def __post_init__(self):
        self.data_dir = os.path.join(TOURNAMENTS_DIR, self.id)
        self.scorecard_cache_dir = os.path.join(self.data_dir, "scorecards")
        self.scores_file = os.path.join(self.data_dir, "cumulative_scores.json")
        self.match_history_file = os.path.join(self.data_dir, "match_history.json")
        self.scoring_sheet_file = os.path.join(self.data_dir, "scoring_sheet.json")
        self.master_scoresheet_file = os.path.join(self.data_dir, "master_scoresheet.json")
        self.teams_file = os.path.join(self.data_dir, "teams_data.json")
        self.players_file = os.path.join(self.data_dir, "players_data.json")
        self.dashboard_prefix = f"/{self.competition}/{self.season}"

    @property
    def short_name(self) -> str:
        """Key used in ?league= query params and file names."""
        return self.id

    @property
    def status_label(self) -> str:
        return STATUS_LABELS.get(self.status, self.status.title())

    @property
    def is_live(self) -> bool:
        return self.status == "live"

    def matches_series(self, series_name: str) -> bool:
        """True if a Cricbuzz series name belongs to this tournament."""
        name = (series_name or "").upper()
        if self.series_year and self.series_year not in name:
            return False
        if any(x.upper() in name for x in self.series_exclude):
            return False
        return any(k.upper() in name for k in self.series_keywords)


_FIELDS = {f for f in Tournament.__dataclass_fields__}
_registry: Optional[Dict[str, Tournament]] = None
_default_id = DEFAULT_TOURNAMENT_ID


def _load() -> Dict[str, Tournament]:
    found: Dict[str, Tournament] = {}
    if not os.path.isdir(TOURNAMENTS_DIR):
        return found
    for tid in sorted(os.listdir(TOURNAMENTS_DIR)):
        path = os.path.join(TOURNAMENTS_DIR, tid, "tournament.json")
        if not os.path.isfile(path):
            continue
        with open(path) as f:
            raw = json.load(f)
        raw["id"] = tid  # folder name is the source of truth
        found[tid] = Tournament(**{k: v for k, v in raw.items() if k in _FIELDS})
    return found


def reload() -> Dict[str, Tournament]:
    global _registry
    _registry = _load()
    return _registry


def all_tournaments() -> List[Tournament]:
    """All tournaments: live first, then auction, upcoming, completed (newest first)."""
    reg = _registry if _registry is not None else reload()
    return sorted(
        reg.values(),
        key=lambda t: (STATUS_ORDER.get(t.status, 9), -int(t.season or 0), t.sort_order, t.id),
    )


def get(tid: str) -> Optional[Tournament]:
    reg = _registry if _registry is not None else reload()
    return reg.get(LEGACY_KEYS.get(tid, tid))


def require(tid: str) -> Tournament:
    t = get(tid)
    if t is None:
        raise KeyError(f"Unknown tournament '{tid}'. Known: {', '.join(sorted(_registry or {}))}")
    return t


def set_default(tid: str) -> Tournament:
    """Make <tid> the tournament used when no tournament is passed (CLI --t)."""
    global _default_id
    t = require(tid)
    _default_id = t.id
    return t


def default() -> Tournament:
    t = get(_default_id)
    if t is None:
        live = [x for x in all_tournaments()]
        if not live:
            raise RuntimeError(f"No tournaments found in {TOURNAMENTS_DIR}")
        t = live[0]
    return t


def from_path(path: str) -> Optional[Tournament]:
    """Find the tournament whose URL prefix the request path starts with."""
    for t in all_tournaments():
        p = t.dashboard_prefix
        if path == p or path.startswith(p + "/"):
            return t
    return None


def legacy_redirect(path: str) -> Optional[str]:
    """Map an old URL (/dashboard/..., /wwc/...) to its new location, else None."""
    for old, new in LEGACY_PREFIXES.items():
        if path.startswith(new + "/") or path == new:
            continue
        if path == old or path.startswith(old + "/"):
            return new + path[len(old):]
    return None


def grouped() -> List[tuple]:
    """[(status_label, [tournaments...]), ...] for the home page."""
    groups: Dict[str, List[Tournament]] = {}
    for t in all_tournaments():
        groups.setdefault(t.status, []).append(t)
    return [(STATUS_LABELS.get(s, s.title()), groups[s])
            for s in sorted(groups, key=lambda s: STATUS_ORDER.get(s, 9))]
