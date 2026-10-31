"""Hacker News "Ask HN: Freelancer? Seeking freelancer?" source.

Every month the ``whoishiring`` bot posts a freelancer thread. Top-level
comments are either:

  * ``SEEKING FREELANCER`` — a client offering a paid gig  (we want these)
  * ``SEEKING WORK``       — a freelancer advertising themselves (we skip)

We use the public, keyless HN Algolia API to find the newest freelancer thread
and read its comments. This is genuinely freelance/contract work, unlike the
full-time remote boards.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

from ..http import get_json
from ..models import JobPosting, Source

SEARCH_URL = (
    "https://hn.algolia.com/api/v1/search"
    "?query=Ask%20HN%20Freelancer%20Seeking%20freelancer"
    "&tags=story,author_whoishiring&hitsPerPage=10"
)
ITEM_URL = "https://hn.algolia.com/api/v1/items/{id}"
_TAG_RE = re.compile(r"<[^>]+>")


def _clean(text: str) -> str:
    text = _TAG_RE.sub(" ", text or "")
    text = (
        text.replace("&#x2F;", "/")
        .replace("&#x27;", "'")
        .replace("&gt;", ">")
        .replace("&lt;", "<")
        .replace("&amp;", "&")
        .replace("&quot;", '"')
    )
    return re.sub(r"\s+", " ", text).strip()


def _find_latest_thread_id() -> str | None:
    try:
        data = get_json(SEARCH_URL)
    except Exception:
        return None
    hits = [
        h for h in data.get("hits", [])
        if (h.get("title") or "").startswith("Ask HN: Freelancer?")
    ]
    if not hits:
        return None
    hits.sort(key=lambda h: h.get("created_at_i", 0), reverse=True)
    return hits[0].get("objectID")


class HackerNewsFreelanceSource(Source):
    name = "hackernews"

    def fetch(self) -> list[JobPosting]:
        thread_id = _find_latest_thread_id()
        if not thread_id:
            return []
        try:
            thread = get_json(ITEM_URL.format(id=thread_id))
        except Exception:
            return []

        postings: list[JobPosting] = []
        for comment in thread.get("children", []):
            text = comment.get("text")
            if not text:
                continue
            upper = text.upper()
            # Only client-posted gigs, not freelancers advertising themselves.
            if "SEEKING FREELANCER" not in upper:
                continue

            cleaned = _clean(text)
            # Build a readable title from the text right after the marker, e.g.
            # "SEEKING FREELANCER - Math & Pencil | Remote | 1099" ->
            # "Math & Pencil | Remote | 1099".
            after = re.split(
                r"(?i)seeking\s+freelancer(?:/consultant)?", cleaned, maxsplit=1
            )
            tail = after[1] if len(after) > 1 else cleaned
            tail = tail.strip(" -|:/")
            # Keep the first ~3 pipe/dash-delimited fields (company/location/type),
            # dropping any trailing prose/URL.
            fields = re.split(r"\s[-|]\s", tail)
            title = " | ".join(f.strip() for f in fields[:3] if f.strip())
            # Strip URLs and collapse.
            title = re.sub(r"https?://\S+", "", title).strip(" |-")
            if not title or len(title) < 3:
                title = "Freelance gig"

            cid = str(comment.get("id", ""))
            created = comment.get("created_at_i")
            posted = (
                datetime.fromtimestamp(created, tz=timezone.utc)
                if created
                else None
            )

            postings.append(
                JobPosting(
                    source=self.name,
                    external_id=cid,
                    title=title[:120],
                    company=comment.get("author", "HN user"),
                    url=f"https://news.ycombinator.com/item?id={cid}",
                    description=cleaned,
                    tags=["freelance", "contract"],
                    location="Remote",
                    rate_type="",
                    posted_at=posted,
                )
            )
        return postings
