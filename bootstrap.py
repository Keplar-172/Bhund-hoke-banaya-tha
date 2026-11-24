#!/usr/bin/env python3
"""Container start-up: prepare the data volume before the app starts.

1. migrate()  One-time move from the old layout (data/*.json, data/wwc/...) into
              data/tournaments/<id>/. The old files are copied to a backup folder
              on the volume first. Safe to run on every start (no-op afterwards).
2. seed()     Copy tournament files from the image's seed copy into the volume:
              - tournament.json            always (settings are managed in git)
              - teams_data / players_data  always if config_source == "git"
                                           and the squads were never changed on the
                                           site (no squad_history.json); otherwise
                                           only when missing
              - everything else            only when missing or empty
                                           (live scores are never overwritten)

Usage:  python bootstrap.py [--data DIR] [--seed DIR]
"""
import argparse
import json
import os
import shutil
from datetime import datetime, timezone

SCORE_FILES = ["cumulative_scores.json", "match_history.json",
               "scoring_sheet.json", "master_scoresheet.json"]
CONFIG_FILES = ["teams_data.json", "players_data.json"]

# old location (relative to data dir) -> tournament id
OLD_LAYOUT = {
    "": "ipl-2026",      # data/*.json, data/scorecards/
    "wwc": "wwc-2026",   # data/wwc/*.json, data/wwc/scorecards/
}


def log(msg: str) -> None:
    print(f"[bootstrap] {msg}", flush=True)


def _old_items(data: str):
    """Yield (src_path, tournament_id, name) for every file/dir in the old layout."""
    for sub, tid in OLD_LAYOUT.items():
        base = os.path.join(data, sub) if sub else data
        names = SCORE_FILES + (CONFIG_FILES if sub else []) + ["scorecards"]
        for name in names:
            src = os.path.join(base, name)
            if os.path.exists(src):
                yield src, tid, name


def migrate(data: str) -> None:
    items = list(_old_items(data))
    if not items:
        log("Layout already up to date.")
        return

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    backup = os.path.join(data, f"_backup_before_tournaments_{stamp}")
    log(f"Old layout found ({len(items)} items). Backing up to {backup}")
    for src, _tid, _name in items:
        rel = os.path.relpath(src, data)
        dst = os.path.join(backup, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if os.path.isdir(src):
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)

    for src, tid, name in items:
        dest_dir = os.path.join(data, "tournaments", tid)
        os.makedirs(dest_dir, exist_ok=True)
        dst = os.path.join(dest_dir, name)
        if os.path.isdir(src):
            os.makedirs(dst, exist_ok=True)
            moved = 0
            for f in os.listdir(src):
                if not os.path.exists(os.path.join(dst, f)):
                    shutil.move(os.path.join(src, f), os.path.join(dst, f))
                    moved += 1
            if not os.listdir(src):
                os.rmdir(src)
            else:
                log(f"  WARNING: {src} not empty after move (duplicates kept in place)")
            log(f"  {os.path.relpath(src, data)}/ -> tournaments/{tid}/{name}/ ({moved} files)")
        elif os.path.exists(dst):
            log(f"  WARNING: {dst} already exists; leaving {src} in place")
        else:
            shutil.move(src, dst)
            log(f"  {os.path.relpath(src, data)} -> tournaments/{tid}/{name}")

    wwc_old = os.path.join(data, "wwc")
    if os.path.isdir(wwc_old) and not os.listdir(wwc_old):
        os.rmdir(wwc_old)
    log("Migration complete.")


def _missing_or_empty(path: str) -> bool:
    return not os.path.exists(path) or os.path.getsize(path) == 0


def seed(data: str, seed_dir: str) -> None:
    src_root = os.path.join(seed_dir, "tournaments")
    dst_root = os.path.join(data, "tournaments")
    if not os.path.isdir(src_root):
        log(f"No seed tournaments at {src_root}; skipping seed.")
        return

    for tid in sorted(os.listdir(src_root)):
        src = os.path.join(src_root, tid)
        if not os.path.isfile(os.path.join(src, "tournament.json")):
            continue
        dst = os.path.join(dst_root, tid)
        os.makedirs(os.path.join(dst, "scorecards"), exist_ok=True)

        with open(os.path.join(src, "tournament.json")) as f:
            from_git = json.load(f).get("config_source", "git") == "git"
        # Once squads have changed on the site (trades, admin edits), the site
        # owns them: never overwrite them from git again.
        if from_git and os.path.exists(os.path.join(dst, "squad_history.json")):
            from_git = False
            log(f"{tid}: squads changed on the site (squad_history.json); not overwriting from git")

        copied = []
        for name in sorted(os.listdir(src)):
            s, d = os.path.join(src, name), os.path.join(dst, name)
            if name == "scorecards" and os.path.isdir(s):
                for sc in os.listdir(s):
                    if _missing_or_empty(os.path.join(d, sc)):
                        shutil.copy2(os.path.join(s, sc), os.path.join(d, sc))
                        copied.append(f"scorecards/{sc}")
                continue
            if not os.path.isfile(s):
                continue
            always = name == "tournament.json" or (name in CONFIG_FILES and from_git)
            if always or _missing_or_empty(d):
                shutil.copy2(s, d)
                copied.append(name)
        summary = ", ".join(c for c in copied if not c.startswith("scorecards/"))
        n_sc = sum(1 for c in copied if c.startswith("scorecards/"))
        log(f"{tid}: synced [{summary or '-'}]" + (f" + {n_sc} scorecards" if n_sc else ""))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data")
    ap.add_argument("--seed", default="data-seed")
    args = ap.parse_args()
    os.makedirs(os.path.join(args.data, "tournaments"), exist_ok=True)
    migrate(args.data)
    seed(args.data, args.seed)
    log("Data directory ready.")


if __name__ == "__main__":
    main()
