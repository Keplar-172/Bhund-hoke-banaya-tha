"""Database for people: accounts, team claims, join links, consent.

SQLite file on the data volume by default (data/gullyxi.db). Set DATABASE_URL
(e.g. a Railway Postgres URL) to move to Postgres later; models don't change.
Scores stay in the JSON files under data/tournaments/.
"""
import os
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker


def _url() -> str:
    url = os.environ.get("DATABASE_URL")
    if url:
        # Railway gives postgres://; SQLAlchemy wants postgresql+psycopg://
        return url.replace("postgres://", "postgresql+psycopg://", 1) \
                  .replace("postgresql://", "postgresql+psycopg://", 1)
    root = os.environ.get("DATA_ROOT", "data")
    os.makedirs(root, exist_ok=True)
    return f"sqlite:///{os.path.join(root, 'gullyxi.db')}"


DB_URL = _url()
IS_SQLITE = DB_URL.startswith("sqlite")
engine = create_engine(DB_URL, connect_args={"check_same_thread": False} if IS_SQLITE else {})

if IS_SQLITE:
    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(conn, _rec):
        cur = conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def init_db() -> None:
    import models  # noqa: F401  (registers tables)
    Base.metadata.create_all(engine)


@contextmanager
def session():
    s = SessionLocal()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def sqlite_path() -> str | None:
    return DB_URL.removeprefix("sqlite:///") if IS_SQLITE else None
