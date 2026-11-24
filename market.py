"""Market settings per tournament: trading window or auction, and its stage.

data/tournaments/<id>/market.json (created by the admin console):
    {"mode": "trading", "stage": "off", "opens_at": "...", "closes_at": "...",
     "note": "...", "rules": {...}}

Stages (only the admin changes them):
    off        hidden from owners (setting up, or finished and hidden)
    scheduled  owners see when it opens; no trading yet
    live       trading open
    paused     visible, but nothing can be offered or accepted
    closed     visible, read-only results / trade log
"""
import json
import os
from datetime import datetime, timezone

STAGES = ["off", "scheduled", "live", "paused", "closed"]
STAGE_LABELS = {"off": "Off (hidden)", "scheduled": "Scheduled", "live": "Live",
                "paused": "Paused", "closed": "Closed"}
DEFAULT_RULES = {
    "offer_expiry_hours": 48,     # open offers lapse after this
    "reversal_hours": 24,         # admin can reverse an accepted trade within this
    "block_during_matches": True, # no trades from match start until it's scored
    "unit": "lakh",               # prices and purses are stored in lakhs
}


def _path(t) -> str:
    return os.path.join(t.data_dir, "market.json")


def load(t) -> dict:
    try:
        with open(_path(t)) as f:
            m = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        m = {}
    m.setdefault("mode", "trading")
    m.setdefault("stage", "off")
    m.setdefault("opens_at", "")
    m.setdefault("closes_at", "")
    m.setdefault("note", "")
    m.setdefault("top_ups", [])
    m.setdefault("cvc_locked", False)   # admin switch: owners can't change C/VC
    m["rules"] = {**DEFAULT_RULES, **m.get("rules", {})}
    return m


def save(t, m: dict) -> None:
    tmp = _path(t) + ".tmp"
    with open(tmp, "w") as f:
        json.dump(m, f, indent=1)
    os.replace(tmp, _path(t))


def update(t, stage: str | None = None, **fields) -> dict:
    m = load(t)
    if stage is not None:
        if stage not in STAGES:
            raise ValueError(f"Unknown stage {stage}")
        m["stage"] = stage
        m.setdefault("stage_log", []).append(
            {"stage": stage, "at": datetime.now(timezone.utc).isoformat(timespec="seconds")})
    if "cvc_locked" in fields and fields["cvc_locked"] is not None:
        m["cvc_locked"] = bool(fields["cvc_locked"])
    for k in ("opens_at", "closes_at", "note", "mode"):
        if k in fields and fields[k] is not None:
            m[k] = str(fields[k])[:300]
    for k, v in (fields.get("rules") or {}).items():
        if k in DEFAULT_RULES:
            m["rules"][k] = v
    save(t, m)
    return m


def cvc_open(t) -> tuple[bool, str]:
    """Can owners change their captain / vice-captain right now? (ok, reason if not)"""
    if t.status in ("live", "completed"):
        return False, "The tournament has started, so captains are locked. Ask the admin if something needs changing."
    if load(t).get("cvc_locked"):
        return False, "The admin has locked captain changes for now."
    return True, ""


def visible(t) -> bool:
    """Do owners see the Market at all?"""
    return load(t)["stage"] != "off"


def is_open(t) -> bool:
    return load(t)["stage"] == "live"


def crores(lakhs) -> str:
    """1625 -> '16.25 cr', 50 -> '0.5 cr'."""
    v = (lakhs or 0) / 100
    s = f"{v:,.2f}".rstrip("0").rstrip(".")
    return f"{s} cr"


def to_lakhs(crore_text: str) -> int:
    """'20' or '20 cr' or '0.25' crores -> lakhs (int). Raises ValueError."""
    txt = (crore_text or "").lower().replace("cr", "").replace(",", "").replace("₹", "").strip()
    if not txt:
        return 0
    val = float(txt)
    if val < 0:
        raise ValueError("Enter the amount without a minus sign and pick who pays.")
    return int(round(val * 100))
