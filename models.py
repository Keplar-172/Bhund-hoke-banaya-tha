"""Tables for people. A User is a person; a Membership links them to the team
they own in one tournament (the owner name used in teams_data.json)."""
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db import Base


def utcnow():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    memberships: Mapped[list["Membership"]] = relationship(
        back_populates="user", cascade="all, delete-orphan")
    consents: Mapped[list["Consent"]] = relationship(
        back_populates="user", cascade="all, delete-orphan")


class Membership(Base):
    """User owns team `owner_name` in tournament `tournament_id`."""
    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("tournament_id", "owner_name"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    tournament_id: Mapped[str] = mapped_column(String(64))
    owner_name: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    user: Mapped[User] = relationship(back_populates="memberships")


class Invite(Base):
    """A join link for one team. Only a hash of the token is stored."""
    __tablename__ = "invites"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    tournament_id: Mapped[str] = mapped_column(String(64))
    owner_name: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    # A re-login link for someone who already claimed (new phone): logs them in.
    for_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)


class Consent(Base):
    """One row per decision, so we can show when and to what someone agreed."""
    __tablename__ = "consents"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    purpose: Mapped[str] = mapped_column(String(32))     # "service_emails" | "news"
    granted: Mapped[bool] = mapped_column(Boolean)
    notice_version: Mapped[str] = mapped_column(String(16))
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    user: Mapped[User] = relationship(back_populates="consents")


class Profile(Base):
    """Optional owner-page details. A separate table so adding it needed no
    change to existing tables (no migrations yet)."""
    __tablename__ = "profiles"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    nickname: Mapped[str | None] = mapped_column(String(40), nullable=True)
    tagline: Mapped[str | None] = mapped_column(String(120), nullable=True)
    fav_team: Mapped[str | None] = mapped_column(String(40), nullable=True)
    fav_player: Mapped[str | None] = mapped_column(String(60), nullable=True)
    city: Mapped[str | None] = mapped_column(String(60), nullable=True)
    plays_as: Mapped[str | None] = mapped_column(String(20), nullable=True)     # gully role
    bio: Mapped[str | None] = mapped_column(String(400), nullable=True)
    avatar_kind: Mapped[str | None] = mapped_column(String(10), nullable=True)  # photo | character
    avatar_char: Mapped[str | None] = mapped_column(String(16), nullable=True)
    avatar_color: Mapped[str | None] = mapped_column(String(16), nullable=True)
    photo_file: Mapped[str | None] = mapped_column(String(80), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class TeamName(Base):
    """Display name for a team, e.g. "Amazon Warriors" for owner key "Mandy".
    The owner key stays the id in score files; only what's shown changes."""
    __tablename__ = "team_names"
    __table_args__ = (UniqueConstraint("tournament_id", "owner_name"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tournament_id: Mapped[str] = mapped_column(String(64))
    owner_name: Mapped[str] = mapped_column(String(80))
    name: Mapped[str | None] = mapped_column(String(40), nullable=True)  # None = show owner key
    updated_by: Mapped[str] = mapped_column(String(80))      # "admin" or "user:<id>"
    # The owner gets one go at naming their team; after that only the admin can change it.
    owner_used: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class TradeOffer(Base):
    """An offer from one team to another: players each way plus cash.
    cash > 0: from_owner pays to_owner; cash < 0: to_owner pays from_owner.
    Money is stored in lakhs (the unit of player prices)."""
    __tablename__ = "trade_offers"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tournament_id: Mapped[str] = mapped_column(String(64), index=True)
    from_owner: Mapped[str] = mapped_column(String(80))
    to_owner: Mapped[str] = mapped_column(String(80))
    cash: Mapped[int] = mapped_column(Integer, default=0)
    message: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # open | accepted | declined | withdrawn | expired | cancelled | countered | reversed
    status: Mapped[str] = mapped_column(String(16), default="open", index=True)
    status_note: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_by: Mapped[str] = mapped_column(String(40))          # "user:<id>" or "admin"
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("trade_offers.id"), nullable=True)
    squad_version: Mapped[int | None] = mapped_column(Integer, nullable=True)   # after accept
    items: Mapped[list["TradeItem"]] = relationship(back_populates="offer", cascade="all, delete-orphan")


class TradeItem(Base):
    """One player in an offer and which side gives him."""
    __tablename__ = "trade_items"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    offer_id: Mapped[int] = mapped_column(ForeignKey("trade_offers.id", ondelete="CASCADE"), index=True)
    player_name: Mapped[str] = mapped_column(String(80))
    giver: Mapped[str] = mapped_column(String(80))      # owner key who gives this player
    offer: Mapped[TradeOffer] = relationship(back_populates="items")
