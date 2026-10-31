# GigRadar — Write-up

## The problem

Freelancers and contractors lose time two ways: refreshing several job boards
every day, and then burning effort on posts that are badly scoped, underpaid,
or outright junk. The good gigs also fill fast — being early matters. I wanted
a tool that aggregates the boards I'd check anyway, filters out the noise, ranks
what's left against *my* criteria, and tells me only about new matches. I picked
this because it's a real itch of my own and it has a genuinely interesting core
(the scoring heuristic) while staying small enough to finish and explain well.

## Approach

GigRadar is a small Python application with four clean stages:

1. **Ingest** — one module per source (Hacker News' monthly freelancer thread,
   Reddit r/forhire, Remotive, We Work Remotely, and optionally RemoteOK), each
   implementing a tiny `Source` interface and mapping its payload onto a single
   normalized `JobPosting` schema.
2. **Score** — pure functions turn a posting into a 0–100 score: stack-keyword
   match (with diminishing returns), contract-fit (freelance vs. full-time
   language), pay vs. a configurable floor, quality signals, recency decay,
   minus red-flag penalties.
3. **Store** — SQLite dedups across runs so only genuinely new postings surface.
4. **Present** — a CLI shows a ranked table and fires a desktop notification for
   high-scorers.

## Key decisions & trade-offs

- **Standard library only, no dependencies.** `urllib`, `xml.etree`, `sqlite3`
  and `tomllib` cover everything. The win is portability — it's truly
  click-and-run on any machine with Python 3.11+, no venv or `pip install`.
  The trade-off is slightly more manual parsing (e.g. regex HTML stripping)
  instead of reaching for `requests`/`feedparser`/`BeautifulSoup`. For this
  scope that was the right call.
- **Dropped Upwork, chose legitimate feeds.** My first instinct was Upwork, but
  it killed its public RSS in Aug 2024 (to stop bot bidding) and scraping it
  violates its terms. I pivoted to public, keyless feeds. This kept the tool
  ethical and ToS-compliant and actually simplified ingestion.
- **Validated against real data, then re-aimed the sources.** My first working
  version leaned on RemoteOK/WWR — but running it showed they return almost
  entirely *full-time* salaried roles, not freelance gigs (0 of 99 RemoteOK
  postings were tagged contract/freelance). Rather than redefine the problem to
  match a weak implementation, I fixed the implementation: added Hacker News'
  monthly freelancer thread and Reddit `[Hiring]` as genuinely freelance
  sources, introduced a **contract-fit** scoring component that rewards
  freelance/hourly language and penalizes salaried-employee language, and turned
  RemoteOK off by default. That's the difference between a job-board aggregator
  and an actual freelance radar.
- **Pure, weighted scoring.** Keeping scoring as side-effect-free functions made
  it unit-testable (22 tests) and easy to tune via config weights. A weighted
  linear model is transparent and explainable — every posting carries its score
  reasons — versus a black-box ML approach that would be overkill here.
- **Unknown pay is neutral, not penalized.** Many legitimate posts omit a rate;
  punishing them would hide good gigs. Red flags, by contrast, are explicit
  negative signals and *do* subtract.
- **SQLite for state.** A single-file DB gives cross-run dedup with zero setup
  and makes scheduling (cron/systemd) trivial.

## How I used AI tools

I used an AI coding assistant to move fast without losing control. It scaffolded
the package layout and boilerplate, drafted the per-source parsers after I
verified each feed's real shape with `curl`, and generated the first pass of the
test suite, which I then reviewed and extended. I drove the architecture
decisions (the `Source` interface, the weighted-scoring design, the
stdlib-only/no-deps constraint, the Upwork pivot) and verified everything by
running the tests and a live end-to-end fetch. The assistant handled volume;
I made the engineering calls.

## What I'd do next

- More sources behind the same interface (Hacker News "Who's hiring", Arbeitnow,
  Himalayas) — each is ~40 lines.
- A proposal-template matcher: suggest a tailored opener per gig type.
- Telegram/email delivery in addition to desktop notifications.
- A tiny web dashboard for browsing/filtering history.
- Smarter rate extraction and optional LLM-assisted scope-quality classification.
