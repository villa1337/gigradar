"""Configuration loading.

Config is a TOML file so it reads cleanly and is easy to hand-edit. We ship a
``config.example.toml`` and fall back to built-in defaults if no config is
found, so the tool runs out of the box with zero setup.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ScoringWeights:
    stack_match: float = 40.0
    rate: float = 25.0
    quality: float = 20.0
    recency: float = 15.0
    red_flag_penalty: float = 30.0


@dataclass
class Config:
    # Keywords that describe the work you want (lowercased on load).
    stack: list[str] = field(
        default_factory=lambda: [
            "python", "aws", "terraform", "java", "cloud", "infrastructure",
            "lambda", "devops", "kubernetes", "api", "backend",
        ]
    )
    # Phrases that indicate a low-quality / risky posting.
    red_flags: list[str] = field(
        default_factory=lambda: [
            "build everything", "do everything", "rockstar", "ninja",
            "unpaid", "equity only", "long term low", "cheap", "lowest bid",
            "urgent urgent", "asap no budget", "simple task huge",
        ]
    )
    # Positive signals of a serious client / well-scoped gig.
    quality_signals: list[str] = field(
        default_factory=lambda: [
            "scope", "milestone", "budget", "long-term", "contract",
            "detailed", "requirements", "documentation", "senior",
        ]
    )
    # Minimum acceptable hourly rate (USD). Postings below score lower.
    min_hourly_rate: float = 50.0
    # Minimum score (0-100) to trigger a desktop notification.
    notify_threshold: float = 70.0
    # Which sources to enable.
    sources: list[str] = field(
        default_factory=lambda: ["remoteok", "remotive", "weworkremotely", "reddit"]
    )
    weights: ScoringWeights = field(default_factory=ScoringWeights)

    def normalized(self) -> "Config":
        self.stack = [s.lower().strip() for s in self.stack if s.strip()]
        self.red_flags = [s.lower().strip() for s in self.red_flags if s.strip()]
        self.quality_signals = [
            s.lower().strip() for s in self.quality_signals if s.strip()
        ]
        return self


def load_config(path: str | Path | None) -> Config:
    """Load config from a TOML file, or return defaults if not provided/found."""
    cfg = Config()
    if path is None:
        return cfg.normalized()
    p = Path(path)
    if not p.exists():
        return cfg.normalized()

    with p.open("rb") as fh:
        data = tomllib.load(fh)

    g = data.get("gigradar", data)
    if "stack" in g:
        cfg.stack = list(g["stack"])
    if "red_flags" in g:
        cfg.red_flags = list(g["red_flags"])
    if "quality_signals" in g:
        cfg.quality_signals = list(g["quality_signals"])
    if "min_hourly_rate" in g:
        cfg.min_hourly_rate = float(g["min_hourly_rate"])
    if "notify_threshold" in g:
        cfg.notify_threshold = float(g["notify_threshold"])
    if "sources" in g:
        cfg.sources = list(g["sources"])

    w = g.get("weights", {})
    if w:
        cfg.weights = ScoringWeights(
            stack_match=float(w.get("stack_match", cfg.weights.stack_match)),
            rate=float(w.get("rate", cfg.weights.rate)),
            quality=float(w.get("quality", cfg.weights.quality)),
            recency=float(w.get("recency", cfg.weights.recency)),
            red_flag_penalty=float(
                w.get("red_flag_penalty", cfg.weights.red_flag_penalty)
            ),
        )
    return cfg.normalized()
