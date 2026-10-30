"""Reddit r/forhire source — public Atom feed, no key/login required.

r/forhire posts are titled like ``[Hiring] Python developer for ...`` or
``[For Hire] ...``. We keep only ``[Hiring]`` posts (people offering work),
since that's what a freelancer monitors.
"""

from __future__ import annotations

import re
from datetime import datetime
from xml.etree import ElementTree as ET

from ..http import get_text
from ..models import JobPosting, Source

FEED_URL = "https://www.reddit.com/r/forhire/new/.rss?limit=100"
_ATOM = "{http://www.w3.org/2005/Atom}"
_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(text: str) -> str:
    return _TAG_RE.sub(" ", text or "").replace("&nbsp;", " ")


def _parse_dt(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


class RedditForHireSource(Source):
    name = "reddit"

    def fetch(self) -> list[JobPosting]:
        try:
            xml = get_text(FEED_URL)
            root = ET.fromstring(xml)
        except Exception:
            return []

        postings: list[JobPosting] = []
        for entry in root.iter(f"{_ATOM}entry"):
            title = (entry.findtext(f"{_ATOM}title") or "").strip()
            # Only keep "hiring" posts (clients offering paid work).
            if "[hiring]" not in title.lower():
                continue

            link_el = entry.find(f"{_ATOM}link")
            url = link_el.get("href") if link_el is not None else ""
            content = _strip_html(entry.findtext(f"{_ATOM}content") or "")
            author = (entry.findtext(f"{_ATOM}author/{_ATOM}name") or "").strip()
            entry_id = (entry.findtext(f"{_ATOM}id") or url).strip()
            published = _parse_dt(entry.findtext(f"{_ATOM}published") or "")

            postings.append(
                JobPosting(
                    source=self.name,
                    external_id=entry_id,
                    title=re.sub(r"(?i)\[hiring\]", "", title).strip(" -"),
                    company=author or "reddit user",
                    url=url,
                    description=content,
                    tags=["forhire"],
                    location="Remote",
                    rate_type="",
                    posted_at=published,
                )
            )
        return postings
