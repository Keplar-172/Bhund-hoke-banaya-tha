"""Team display names chosen by owners (or the admin).

The owner key ("Mandy") stays the id everywhere in the score files; this only
changes what is shown: "Amazon Warriors" with "Mandy" underneath.
Names are cached per tournament and the cache is cleared on every change
(the app runs as a single process).
"""
import re
import threading

from sqlalchemy import select

import db
from models import TeamName

MIN_LEN, MAX_LEN = 2, 30
_cache: dict = {}
_lock = threading.Lock()


def names(tournament_id: str) -> dict:
    """{owner_key: team name} for teams that have one."""
    with _lock:
        if tournament_id in _cache:
            return _cache[tournament_id]
    with db.session() as s:
        out = {r.owner_name: r.name for r in s.scalars(
            select(TeamName).where(TeamName.tournament_id == tournament_id)) if r.name}
    with _lock:
        _cache[tournament_id] = out
    return out


def display(tournament_id: str, owner: str) -> str:
    return names(tournament_id).get(owner) or owner


def clean(name: str) -> str:
    return re.sub(r"\s+", " ", (name or "").strip())


class NeedsAdmin(ValueError):
    """The owner has already used their one rename."""


def owner_can_rename(tournament_id: str, owner: str) -> bool:
    with db.session() as s:
        row = s.scalar(select(TeamName).where(TeamName.tournament_id == tournament_id,
                                              TeamName.owner_name == owner))
        return not (row and row.owner_used)


def set_name(tournament_id: str, owner: str, name: str, all_owners: list, by: str,
             is_admin: bool = False) -> str | None:
    """Set (or clear, with an empty name) a team's name. Returns the new name.

    The owner can do this once; the admin any number of times.
    Raises ValueError (or NeedsAdmin) with a friendly message."""
    if not is_admin and not owner_can_rename(tournament_id, owner):
        raise NeedsAdmin("You've already named your team. To change it, ask the admin.")
    name = clean(name)
    if name and not (MIN_LEN <= len(name) <= MAX_LEN):
        raise ValueError(f"Team names are {MIN_LEN} to {MAX_LEN} characters.")
    if name and not re.search(r"[A-Za-z0-9]", name):
        raise ValueError("Use at least one letter or number.")
    if name:
        taken = {v.lower() for k, v in names(tournament_id).items() if k != owner}
        taken |= {o.lower() for o in all_owners if o != owner}
        if name.lower() in taken:
            raise ValueError("Another team in this league already uses that name.")
    with db.session() as s:
        row = s.scalar(select(TeamName).where(TeamName.tournament_id == tournament_id,
                                              TeamName.owner_name == owner))
        if not name or name == owner:
            name = None
        if row is None:
            row = TeamName(tournament_id=tournament_id, owner_name=owner, owner_used=False)
            s.add(row)
        row.name, row.updated_by = name, by
        if not is_admin:
            row.owner_used = True
    with _lock:
        _cache.pop(tournament_id, None)
    return name


def allow_owner_again(tournament_id: str, owner: str) -> None:
    """Admin: give the owner one more go at naming their team."""
    with db.session() as s:
        row = s.scalar(select(TeamName).where(TeamName.tournament_id == tournament_id,
                                              TeamName.owner_name == owner))
        if row:
            row.owner_used = False
