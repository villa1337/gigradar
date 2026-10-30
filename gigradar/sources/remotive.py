"""Remotive source — public JSON API, no key required.

https://remotive.com/api/remote-jobs returns {"jobs": [...]}.
"""

from __future__ import annotations

from datetime import datetime

from ..http import get_json
from ..models import JobPosting, Source

API_URL = "https://remotive.com/api/remote-jobs?limit=100"


def _parse_date(value: str) -> datetime | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(value[: len(fmt) + 0], fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


class RemotiveSource(Source):
    name = "remotive"

    def fetch(self) -> list[JobPosting]:
        try:
            data = get_json(API_URL)
        except Exception:
            return []
        jobs = data.get("jobs", []) if isinstance(data, dict) else []

        postings: list[JobPosting] = []
        for item in jobs:
            if not isinstance(item, dict):
                continue
            postings.append(
                JobPosting(
                    source=self.name,
                    external_id=str(item.get("id", "")),
                    title=(item.get("title") or "").strip(),
                    company=(item.get("company_name") or "").strip(),
                    url=item.get("url", ""),
                    description=item.get("description", "") or "",
                    tags=[str(t) for t in item.get("tags", []) if t],
                    location=item.get("candidate_required_location", "") or "Remote",
                    rate_type="annual",
                    posted_at=_parse_date(item.get("publication_date", "")),
                )
            )
        return postings
