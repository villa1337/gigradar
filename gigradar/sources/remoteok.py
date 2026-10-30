"""RemoteOK source — public JSON API, no key required.

https://remoteok.com/api returns a JSON array whose first element is a
legal/metadata object; the rest are job postings.
"""

from __future__ import annotations

from datetime import datetime, timezone

from ..http import get_json
from ..models import JobPosting, Source

API_URL = "https://remoteok.com/api"


def _parse_epoch(value) -> datetime | None:
    try:
        return datetime.fromtimestamp(int(value), tz=timezone.utc)
    except (TypeError, ValueError):
        return None


def _to_float(value):
    try:
        if value in (None, "", 0, "0"):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


class RemoteOKSource(Source):
    name = "remoteok"

    def fetch(self) -> list[JobPosting]:
        try:
            data = get_json(API_URL)
        except Exception:
            return []
        if not isinstance(data, list):
            return []

        postings: list[JobPosting] = []
        for item in data:
            # Skip the leading legal/metadata object.
            if not isinstance(item, dict) or "position" not in item:
                continue
            postings.append(
                JobPosting(
                    source=self.name,
                    external_id=str(item.get("id", "")),
                    title=item.get("position", "").strip(),
                    company=item.get("company", "").strip(),
                    url=item.get("url", "")
                    or f"https://remoteok.com/remote-jobs/{item.get('id', '')}",
                    description=item.get("description", "") or "",
                    tags=[str(t) for t in item.get("tags", []) if t],
                    location=item.get("location", "") or "Remote",
                    salary_min=_to_float(item.get("salary_min")),
                    salary_max=_to_float(item.get("salary_max")),
                    rate_type="annual",
                    posted_at=_parse_epoch(item.get("epoch")),
                )
            )
        return postings
