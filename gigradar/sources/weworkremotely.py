"""We Work Remotely source — public RSS 2.0 feed, no key required.

Items look like ``<title>Company: Role</title>`` plus region/description/link.
Parsed with stdlib ``xml.etree.ElementTree``.
"""

from __future__ import annotations

import re
from datetime import datetime
from xml.etree import ElementTree as ET

from ..http import get_text
from ..models import JobPosting, Source

# Programming category RSS. Swap/extend categories freely.
FEED_URL = "https://weworkremotely.com/categories/remote-programming-jobs.rss"
_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(text: str) -> str:
    return _TAG_RE.sub(" ", text or "").replace("&nbsp;", " ")


def _parse_pubdate(value: str) -> datetime | None:
    if not value:
        return None
    for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S %Z"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


class WeWorkRemotelySource(Source):
    name = "weworkremotely"

    def fetch(self) -> list[JobPosting]:
        try:
            xml = get_text(FEED_URL)
            root = ET.fromstring(xml)
        except Exception:
            return []

        postings: list[JobPosting] = []
        for item in root.iter("item"):
            title_raw = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            region = (item.findtext("region") or "").strip()
            category = (item.findtext("category") or "").strip()
            desc = _strip_html(item.findtext("description") or "")
            pubdate = _parse_pubdate(item.findtext("pubDate") or "")

            # Title is usually "Company: Role".
            company, _, role = title_raw.partition(":")
            if role:
                company, title = company.strip(), role.strip()
            else:
                company, title = "", title_raw

            postings.append(
                JobPosting(
                    source=self.name,
                    external_id=link,
                    title=title,
                    company=company,
                    url=link,
                    description=desc,
                    tags=[t for t in [category] if t],
                    location=region or "Remote",
                    rate_type="annual",
                    posted_at=pubdate,
                )
            )
        return postings
