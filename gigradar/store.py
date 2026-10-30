"""SQLite persistence: dedup + state so re-runs only surface *new* postings.

We use the stdlib ``sqlite3`` module — no external dependency, and the DB is a
single portable file (default ``~/.local/share/gigradar/gigradar.db``).
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .models import JobPosting

SCHEMA = """
CREATE TABLE IF NOT EXISTS postings (
    uid          TEXT PRIMARY KEY,
    source       TEXT NOT NULL,
    external_id  TEXT,
    title        TEXT,
    company      TEXT,
    url          TEXT,
    location     TEXT,
    tags         TEXT,
    salary_min   REAL,
    salary_max   REAL,
    rate_type    TEXT,
    posted_at    TEXT,
    score        REAL,
    score_reasons TEXT,
    first_seen   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_postings_score ON postings(score DESC);
CREATE INDEX IF NOT EXISTS idx_postings_first_seen ON postings(first_seen DESC);
"""


def default_db_path() -> Path:
    base = Path.home() / ".local" / "share" / "gigradar"
    base.mkdir(parents=True, exist_ok=True)
    return base / "gigradar.db"


class Store:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else default_db_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.path))
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "Store":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def exists(self, uid: str) -> bool:
        cur = self.conn.execute("SELECT 1 FROM postings WHERE uid = ?", (uid,))
        return cur.fetchone() is not None

    def upsert_new(self, posting: JobPosting) -> bool:
        """Insert a posting if unseen. Returns True if it was new."""
        if self.exists(posting.uid):
            return False
        self.conn.execute(
            """INSERT INTO postings
               (uid, source, external_id, title, company, url, location, tags,
                salary_min, salary_max, rate_type, posted_at, score,
                score_reasons, first_seen)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                posting.uid,
                posting.source,
                posting.external_id,
                posting.title,
                posting.company,
                posting.url,
                posting.location,
                json.dumps(posting.tags),
                posting.salary_min,
                posting.salary_max,
                posting.rate_type,
                posting.posted_iso(),
                posting.score,
                json.dumps(posting.score_reasons),
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        self.conn.commit()
        return True

    def top(self, limit: int = 20, min_score: float = 0.0) -> list[dict]:
        cur = self.conn.execute(
            """SELECT * FROM postings WHERE score >= ?
               ORDER BY score DESC, first_seen DESC LIMIT ?""",
            (min_score, limit),
        )
        return [dict(r) for r in cur.fetchall()]

    def count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM postings").fetchone()[0]
