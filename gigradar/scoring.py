"""Scoring engine — the heart of GigRadar.

Given a :class:`JobPosting` and a :class:`Config`, produce a 0-100 score plus
human-readable reasons. The score is a weighted sum of four positive
components minus a red-flag penalty:

    score = stack_match*w1 + rate*w2 + quality*w3 + recency*w4 - redflags*w5

Each component is first computed on a normalized 0..1 scale, then multiplied by
its configured weight. The final score is clamped to 0..100. Keeping these as
pure functions (no I/O) makes the logic easy to unit-test and reason about.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

from .config import Config
from .models import JobPosting

# Hourly-rate detector, e.g. "$75/hr", "$80 per hour", "80 USD/hour".
_HOURLY_RE = re.compile(
    r"\$?\s*(\d{2,3})(?:\s*[-–to]+\s*\$?\s*(\d{2,3}))?\s*(?:/|\s*per\s*)\s*(?:hr|hour)",
    re.IGNORECASE,
)
# Annual salary detector, e.g. "$120,000", "120k", "$90k-$120k".
_ANNUAL_RE = re.compile(r"\$?\s*(\d{2,3})\s*[kK]\b")


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def stack_match_score(posting: JobPosting, cfg: Config) -> tuple[float, list[str]]:
    """Fraction of configured stack keywords present, with diminishing returns.

    One match is good; several is better but we don't want a posting that spams
    every keyword to dominate, so we use sqrt-like saturation.
    """
    hay = posting.haystack
    hits = [kw for kw in cfg.stack if kw and kw in hay]
    if not cfg.stack:
        return 0.0, []
    # Saturating curve: 0 -> 0, 1 -> 0.5, 2 -> 0.7, 3 -> 0.82, >=5 -> ~1.
    n = len(hits)
    raw = 1.0 - (0.5 ** n) if n else 0.0
    reasons = [f"stack: {', '.join(hits)}"] if hits else []
    return _clamp01(raw), reasons


def extract_hourly_rate(text: str) -> float | None:
    """Best (highest) hourly rate found in free text, else None."""
    best: float | None = None
    for m in _HOURLY_RE.finditer(text):
        lo = float(m.group(1))
        hi = float(m.group(2)) if m.group(2) else lo
        cand = max(lo, hi)
        if best is None or cand > best:
            best = cand
    return best


def rate_score(posting: JobPosting, cfg: Config) -> tuple[float, list[str]]:
    """Score pay against the configured floor.

    Prefers structured salary fields; falls back to parsing the description.
    Unknown pay is neutral (0.5) rather than punished — absence of data is not
    evidence of a bad gig.
    """
    floor = cfg.min_hourly_rate

    # 1) Structured hourly.
    if posting.rate_type == "hourly" and posting.salary_max:
        rate = posting.salary_max
        s = _clamp01(rate / (floor * 2)) if floor else 1.0
        return s, [f"hourly ${rate:.0f} (floor ${floor:.0f})"]

    # 2) Structured annual -> approximate hourly (2080 work hours/yr).
    if posting.rate_type == "annual" and (posting.salary_max or posting.salary_min):
        annual = posting.salary_max or posting.salary_min or 0.0
        approx_hourly = annual / 2080.0
        s = _clamp01(approx_hourly / (floor * 2)) if floor else 1.0
        return s, [f"~${approx_hourly:.0f}/hr from ${annual:,.0f}/yr"]

    # 3) Parse hourly from text.
    rate = extract_hourly_rate(posting.haystack)
    if rate is not None:
        s = _clamp01(rate / (floor * 2)) if floor else 1.0
        tag = f"found ${rate:.0f}/hr"
        if rate < floor:
            tag += " (below floor)"
        return s, [tag]

    # 4) Parse annual "k" from text.
    m = _ANNUAL_RE.search(posting.haystack)
    if m:
        annual = float(m.group(1)) * 1000
        approx_hourly = annual / 2080.0
        s = _clamp01(approx_hourly / (floor * 2)) if floor else 1.0
        return s, [f"~${approx_hourly:.0f}/hr from ${annual:,.0f}/yr"]

    # Unknown pay: neutral.
    return 0.5, ["pay not stated"]


def quality_score(posting: JobPosting, cfg: Config) -> tuple[float, list[str]]:
    """Positive signals of a serious, well-scoped client."""
    hay = posting.haystack
    hits = [kw for kw in cfg.quality_signals if kw and kw in hay]
    bonus = 0.0
    reasons: list[str] = []
    if hits:
        reasons.append(f"signals: {', '.join(hits)}")
    # A substantive description is itself a quality signal.
    if len(posting.description) > 400:
        bonus += 0.2
        reasons.append("detailed description")
    base = _clamp01(len(hits) / 3.0)
    return _clamp01(base + bonus), reasons


def recency_score(posting: JobPosting, now: datetime | None = None) -> tuple[float, list[str]]:
    """Fresher postings score higher; good gigs fill fast. Linear decay over 14 days."""
    if posting.posted_at is None:
        return 0.5, []
    now = now or datetime.now(timezone.utc)
    posted = posting.posted_at
    if posted.tzinfo is None:
        posted = posted.replace(tzinfo=timezone.utc)
    age_days = (now - posted).total_seconds() / 86400.0
    if age_days < 0:
        age_days = 0.0
    s = _clamp01(1.0 - age_days / 14.0)
    return s, [f"posted {age_days:.1f}d ago"] if age_days else ["posted today"]


def red_flag_score(posting: JobPosting, cfg: Config) -> tuple[float, list[str]]:
    """Fraction (0..1) indicating how many red-flag phrases appear.

    Returned value is a *penalty magnitude*; higher means worse.
    """
    hay = posting.haystack
    hits = [p for p in cfg.red_flags if p and p in hay]
    if not hits:
        return 0.0, []
    # Each flag adds, saturating at 1.0.
    mag = _clamp01(len(hits) / 3.0)
    return mag, [f"RED FLAGS: {', '.join(hits)}"]


def score_posting(posting: JobPosting, cfg: Config, now: datetime | None = None) -> JobPosting:
    """Compute the weighted score and attach it (plus reasons) to the posting."""
    w = cfg.weights
    stack_s, stack_r = stack_match_score(posting, cfg)
    rate_s, rate_r = rate_score(posting, cfg)
    qual_s, qual_r = quality_score(posting, cfg)
    rec_s, rec_r = recency_score(posting, now)
    flag_s, flag_r = red_flag_score(posting, cfg)

    raw = (
        stack_s * w.stack_match
        + rate_s * w.rate
        + qual_s * w.quality
        + rec_s * w.recency
        - flag_s * w.red_flag_penalty
    )
    posting.score = round(max(0.0, min(100.0, raw)), 1)
    posting.score_reasons = stack_r + rate_r + qual_r + rec_r + flag_r
    return posting
