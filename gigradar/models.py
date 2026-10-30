"""Core data model and source interface for GigRadar.

A single normalized ``JobPosting`` schema is used across every source so the
scoring engine and storage layer never have to care where a posting came from.
"""

from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class JobPosting:
    """A normalized job/gig posting.

    Every ingester maps its source-specific payload onto this schema. The
    ``uid`` is a stable hash used for deduplication across runs.
    """

    source: str
    external_id: str
    title: str
    company: str
    url: str
    description: str = ""
    tags: list[str] = field(default_factory=list)
    location: str = ""
    # Normalized pay info. We store whatever the source exposes; the scorer
    # handles missing values gracefully.
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    rate_type: str = ""  # "hourly" | "annual" | "fixed" | ""
    posted_at: Optional[datetime] = None

    # Populated by the scoring engine (not by ingesters).
    score: float = 0.0
    score_reasons: list[str] = field(default_factory=list)

    @property
    def uid(self) -> str:
        """Stable identifier for dedup: source + external id (falls back to URL)."""
        basis = f"{self.source}:{self.external_id or self.url}"
        return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:16]

    @property
    def haystack(self) -> str:
        """Lowercased blob of searchable text used by the scorer."""
        return " ".join(
            [self.title, self.company, self.description, " ".join(self.tags)]
        ).lower()

    def posted_iso(self) -> str:
        if self.posted_at is None:
            return ""
        return self.posted_at.astimezone(timezone.utc).isoformat()


class Source(ABC):
    """Common interface every ingester implements.

    Keeping this tiny makes adding a new job board a ~40-line change: implement
    ``fetch()`` returning normalized ``JobPosting`` objects.
    """

    #: Short, stable name used in storage and the UI (e.g. "remoteok").
    name: str = "source"

    @abstractmethod
    def fetch(self) -> list[JobPosting]:
        """Return normalized postings. Network/parse errors should be caught
        and surfaced as an empty list so one broken source never kills a run."""
        raise NotImplementedError
