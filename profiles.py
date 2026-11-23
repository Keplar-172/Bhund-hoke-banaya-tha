"""Owner pages: optional profile details, photo or character avatar.

Photos are re-encoded to a 400x400 JPEG (which also drops EXIF data such as
the GPS location phones add) and stored on the data volume under
uploads/avatars/. They are only served to logged-in users.
"""
import io
import os
import re
import secrets

from sqlalchemy import select

import db
from models import Membership, Profile, User

# Characters: emoji on a coloured disc. Original set, no real-team branding.
CHARACTERS = {
    "bat": "🏏", "ball": "🥎", "gloves": "🧤", "cap": "🧢", "trophy": "🏆", "fire": "🔥",
    "bolt": "⚡", "lion": "🦁", "tiger": "🐯", "eagle": "🦅", "shark": "🦈", "wolf": "🐺",
    "fox": "🦊", "panda": "🐼", "elephant": "🐘", "dragon": "🐉", "rocket": "🚀", "crown": "👑",
}
COLORS = {"ball": "#D7EA3B", "teal": "#157A7A", "brick": "#C2452D", "sky": "#4A90C2",
          "gold": "#D99A1E", "ink": "#1E2A31", "rose": "#C24A7A", "leaf": "#3F8A3A"}
DARK_TEXT_COLORS = {"ball", "gold"}
PLAYS_AS = ["Batter", "Bowler", "All-rounder", "Keeper", "Captain", "Umpire", "Cheerleader"]
FAV_TEAMS = ["CSK", "MI", "RCB", "KKR", "SRH", "RR", "DC", "PBKS", "LSG", "GT",
             "India", "Australia", "England", "New Zealand", "South Africa"]
TEXT_FIELDS = {"nickname": 40, "tagline": 120, "fav_team": 40,
               "fav_player": 60, "city": 60, "bio": 400}

MAX_UPLOAD = 8 * 1024 * 1024
PHOTO_SIZE = 400
_FILE_RE = re.compile(r"^u\d+-[A-Za-z0-9_-]{8,}\.jpg$")


def avatar_dir() -> str:
    d = os.path.join(os.environ.get("DATA_ROOT", "data"), "uploads", "avatars")
    os.makedirs(d, exist_ok=True)
    return d


def valid_photo_name(name: str) -> bool:
    return bool(_FILE_RE.match(name or ""))


def _initials(name: str) -> str:
    parts = [p for p in re.split(r"\s+", (name or "").strip()) if p]
    return ("".join(p[0] for p in parts[:2]) or "?").upper()


def _view(user: User, p: Profile | None) -> dict:
    """Everything a template needs to show a person."""
    p_dict = {f: getattr(p, f) if p else None for f in TEXT_FIELDS}
    p_dict["plays_as"] = p.plays_as if p else None
    color_key = (p.avatar_color if p else None) or "teal"
    avatar = {"kind": "initials", "text": _initials(user.name),
              "bg": COLORS.get(color_key, COLORS["teal"]),
              "dark_text": color_key in DARK_TEXT_COLORS}
    if p and p.avatar_kind == "photo" and p.photo_file:
        avatar = {"kind": "photo", "src": f"/media/avatars/{p.photo_file}"}
    elif p and p.avatar_kind == "character" and p.avatar_char in CHARACTERS:
        avatar.update(kind="character", text=CHARACTERS[p.avatar_char])
    return {"user_id": user.id, "name": user.name, "display": p_dict["nickname"] or user.name,
            **p_dict, "avatar": avatar,
            "avatar_kind": p.avatar_kind if p else None,
            "avatar_char": p.avatar_char if p else None, "avatar_color": color_key,
            "teams": [{"tournament_id": m.tournament_id, "owner_name": m.owner_name}
                      for m in user.memberships]}


def get(user_id: int) -> dict | None:
    with db.session() as s:
        u = s.get(User, user_id)
        if u is None:
            return None
        return _view(u, s.get(Profile, user_id))


def for_teams(tournament_id: str) -> dict:
    """{owner_name: person view} for every claimed team in a tournament."""
    with db.session() as s:
        out = {}
        for m in s.scalars(select(Membership).where(Membership.tournament_id == tournament_id)):
            out[m.owner_name] = _view(m.user, s.get(Profile, m.user_id))
        return out


def update(user_id: int, form: dict) -> None:
    with db.session() as s:
        p = s.get(Profile, user_id) or Profile(user_id=user_id)
        for field, limit in TEXT_FIELDS.items():
            val = (form.get(field) or "").strip()[:limit]
            setattr(p, field, val or None)
        plays = form.get("plays_as") or ""
        p.plays_as = plays if plays in PLAYS_AS else None
        kind = form.get("avatar_kind")
        if kind == "character":
            p.avatar_kind = "character"
            p.avatar_char = form.get("avatar_char") if form.get("avatar_char") in CHARACTERS else "bat"
        elif kind == "photo" and p.photo_file:
            p.avatar_kind = "photo"
        elif kind == "initials":
            p.avatar_kind = None
        color = form.get("avatar_color")
        if color in COLORS:
            p.avatar_color = color
        s.add(p)


def save_photo(user_id: int, data: bytes) -> None:
    """Validate, square-crop, resize and store a photo. Raises ValueError."""
    from PIL import Image, ImageOps, UnidentifiedImageError
    if not data:
        raise ValueError("Choose a photo first.")
    if len(data) > MAX_UPLOAD:
        raise ValueError("That photo is too big (max 8 MB).")
    Image.MAX_IMAGE_PIXELS = 40_000_000
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError):
        raise ValueError("That file isn't a photo we can read. Try a JPEG or PNG.")
    img = ImageOps.exif_transpose(img).convert("RGB")
    img = ImageOps.fit(img, (PHOTO_SIZE, PHOTO_SIZE), Image.LANCZOS)
    name = f"u{user_id}-{secrets.token_urlsafe(9)}.jpg"
    img.save(os.path.join(avatar_dir(), name), "JPEG", quality=85, optimize=True)  # no EXIF kept

    with db.session() as s:
        p = s.get(Profile, user_id) or Profile(user_id=user_id)
        old = p.photo_file
        p.photo_file, p.avatar_kind = name, "photo"
        s.add(p)
    _remove_file(old)


def remove_photo(user_id: int) -> None:
    with db.session() as s:
        p = s.get(Profile, user_id)
        if not p:
            return
        old, p.photo_file = p.photo_file, None
        if p.avatar_kind == "photo":
            p.avatar_kind = None
    _remove_file(old)


def delete_files_for(user_id: int) -> None:
    """Called when an account is deleted."""
    with db.session() as s:
        p = s.get(Profile, user_id)
        old = p.photo_file if p else None
    _remove_file(old)


def _remove_file(name: str | None) -> None:
    if name and valid_photo_name(name):
        try:
            os.remove(os.path.join(avatar_dir(), name))
        except FileNotFoundError:
            pass
