# GigRadar 🛰️

A portable freelance / remote-gig monitor. It polls several public job feeds,
scores every posting against **your** stack and quality signals, drops the
red-flag junk, remembers what it has already seen, and surfaces only the best
**new** matches — with an optional desktop notification.

Good gigs fill in hours. GigRadar turns "scroll five job boards every morning"
into one command.

```
GigRadar 1.0.0 — fetching 4 source(s)…
  hackernews         15 postings
  reddit             15 postings
  remotive           12 postings
  weworkremotely     25 postings

Fetched 67 | new 67 | stored 67
  ★  72.1  Philadelphia & New York | Remote US        [hackernews]
  ★  70.5  Boulder, CO | Remote | US Time Zone         [hackernews]
  ★  69.2  Flanksource | Remote First                  [hackernews]
  ★  64.1  Utility Operations Application Specialist   [reddit]
```

## Why this exists

Freelancers and contractors waste time refreshing multiple job boards and still
waste effort on badly-scoped or underpaid posts. GigRadar automates the boring
part — aggregation, filtering and ranking — so you only look at gigs worth your
time, and you see them fast.

## Quick start (click-and-run)

**Requirements:** Python **3.11+** only. No `pip install`, no virtualenv, no
API keys. Everything uses the Python standard library.

```bash
# 1. Fetch, score and store new postings from all sources
./run.sh
#   (equivalently: python3 -m gigradar run)

# 2. Show the ranked results
./run.sh list --min-score 60
#   (equivalently: python3 -m gigradar list --min-score 60)
```

On Windows (no bash):

```powershell
python3 -m gigradar run
python3 -m gigradar list --min-score 60
```

That's it. The first run stores everything it finds; later runs only report
what's **new** since last time.

## Commands

| Command | What it does |
| --- | --- |
| `run` | Fetch all enabled sources, score, store new postings, notify on high-scorers. |
| `list` | Print the ranked table of stored postings. |
| `sources` | List available sources. |

Useful flags:

```bash
python3 -m gigradar run --no-notify           # skip desktop notifications
python3 -m gigradar list -n 15 -m 60 -v       # top 15, score >= 60, show URLs
python3 -m gigradar --config config.toml run  # use a custom config
python3 -m gigradar --db ./my.db run          # use a custom database file
```

## Configuration (optional)

GigRadar runs with sensible defaults out of the box. To tailor it, copy the
example and edit it:

```bash
cp config.example.toml config.toml
python3 -m gigradar --config config.toml run
```

You can set your `stack` keywords, `min_hourly_rate`, `red_flags`,
`quality_signals`, which `sources` to poll, the `notify_threshold`, and the
scoring `weights`. See [`config.example.toml`](config.example.toml) for the
full annotated list.

## How scoring works

Each posting gets a **0–100** score from a weighted sum of five positive
components minus a red-flag penalty:

```
score = stack_match·30 + contract·25 + rate·20 + quality·15 + recency·10 − red_flags·30
```

- **Stack match** — how many of your stack keywords appear (diminishing returns
  so one keyword-stuffed post can't dominate).
- **Contract fit** — rewards genuine freelance/contract/hourly language and
  penalizes full-time salaried-employee language (401k, benefits, W-2). This is
  what keeps GigRadar aimed at *gigs* rather than full-time roles.
- **Rate** — pay vs. your floor. Uses structured salary fields when present,
  otherwise parses `$/hr` or `$Nk` from the text. Unknown pay is treated as
  neutral, not punished.
- **Quality** — signals of a serious client (scope, milestones, budget,
  detailed description).
- **Recency** — newer is better; linear decay over 14 days.
- **Red flags** — "build everything", "unpaid", "rockstar/ninja", etc. subtract.

All scoring functions are pure (no I/O), which makes them easy to test and
tune — see [`gigradar/scoring.py`](gigradar/scoring.py).

## Data sources

All sources are **public and keyless**. GigRadar is a *freelance* monitor, so
the genuinely freelance sources are enabled by default and the full-time remote
boards are opt-in:

| Source | Type | Default | Notes |
| --- | --- | --- | --- |
| Hacker News | JSON API | ✅ on | Monthly "Freelancer? Seeking freelancer?" thread — real client gigs. |
| Reddit r/forhire | Atom | ✅ on | Filtered to `[Hiring]` posts (clients offering paid work). |
| Remotive | JSON API | ✅ on | Remote software jobs (contract + full-time; scorer sorts it out). |
| We Work Remotely | RSS 2.0 | ✅ on | Remote programming category. |
| RemoteOK | JSON API | ⬜ off | Almost entirely full-time salaried roles; enable in config if wanted. |

> **Why these sources?** My first cut leaned on RemoteOK/WWR, but checking the
> live data showed they return mostly *full-time* salaried roles, not freelance
> gigs. I re-aimed at genuinely freelance feeds (Hacker News' freelancer thread,
> Reddit `[Hiring]`) and added a **contract-fit** scoring component so true gigs
> outrank salaried roles. RemoteOK is still available but off by default.
>
> **Note on Upwork:** Upwork discontinued its public RSS feeds in August 2024
> (to curb automated bidding), and scraping its site violates its terms.
> GigRadar deliberately uses only legitimate, public feeds. Adding a new source
> is a ~40-line file implementing the `Source` interface.

## Architecture

```
gigradar/
├── models.py        # JobPosting schema + Source interface
├── config.py        # TOML config + defaults
├── http.py          # stdlib urllib helper
├── scoring.py       # pure scoring functions (the core)
├── store.py         # SQLite dedup + state
├── notify.py        # cross-platform desktop notifications
├── cli.py           # argparse CLI (run / list / sources)
└── sources/         # one file per job board, behind a common interface
    ├── hackernews.py
    ├── reddit.py
    ├── remotive.py
    ├── weworkremotely.py
    └── remoteok.py
tests/
└── test_scoring.py  # 26 unit tests, stdlib unittest
```

The flow: **sources** fetch and normalize → **scoring** ranks → **store** dedups
and persists → **cli** presents and notifies.

## Scheduling (optional)

Run it every 30 minutes with cron:

```cron
*/30 * * * * cd /path/to/gigradar && ./run.sh >/dev/null 2>&1
```

Or a systemd timer, or Task Scheduler on Windows. The dedup store means it only
notifies you about genuinely new postings.

## Tests

```bash
python3 -m unittest discover -s tests -v
```

26 tests cover stack matching, the contract-fit classifier, rate parsing,
quality/recency/red-flag scoring, and end-to-end ranking — all stdlib, nothing
to install.

## Storage

State lives in a single SQLite file (default
`~/.local/share/gigradar/gigradar.db`). Delete it to reset, or point elsewhere
with `--db`.

## License

MIT.
