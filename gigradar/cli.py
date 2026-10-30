"""GigRadar command-line interface.

Commands:
    run     Fetch all enabled sources, score, store new postings, notify.
    list    Show the ranked table of stored postings.
    sources List available sources.

Run with ``python3 -m gigradar <command>``.
"""

from __future__ import annotations

import argparse
import sys
import textwrap

from . import __version__
from .config import load_config
from .notify import notify
from .scoring import score_posting
from .sources import available_source_names, build_sources
from .store import Store, default_db_path


def _truncate(text: str, width: int) -> str:
    text = (text or "").replace("\n", " ").strip()
    return text if len(text) <= width else text[: width - 1] + "…"


def cmd_run(args) -> int:
    cfg = load_config(args.config)
    sources = build_sources(cfg.sources)
    if not sources:
        print("No valid sources configured.", file=sys.stderr)
        return 1

    print(f"GigRadar {__version__} — fetching {len(sources)} source(s)…")
    all_postings = []
    for src in sources:
        items = src.fetch()
        print(f"  {src.name:16} {len(items):4d} postings")
        all_postings.extend(items)

    new_count = 0
    high_scorers = []
    with Store(args.db) as store:
        for p in all_postings:
            score_posting(p, cfg)
            if store.upsert_new(p):
                new_count += 1
                if p.score >= cfg.notify_threshold:
                    high_scorers.append(p)

        total = store.count()

    print(f"\nFetched {len(all_postings)} | new {new_count} | stored {total}")

    for p in sorted(high_scorers, key=lambda x: x.score, reverse=True):
        print(f"  ★ {p.score:5.1f}  {_truncate(p.title, 45)}  [{p.source}]")

    if high_scorers and not args.no_notify:
        top = max(high_scorers, key=lambda x: x.score)
        notify(
            f"GigRadar: {len(high_scorers)} new match(es)",
            f"{top.score:.0f} — {top.title} ({top.company})",
        )
    return 0


def cmd_list(args) -> int:
    cfg = load_config(args.config)
    with Store(args.db) as store:
        rows = store.top(limit=args.limit, min_score=args.min_score)
        total = store.count()

    if not rows:
        print("No postings stored yet. Run:  python3 -m gigradar run")
        return 0

    print(f"Top {len(rows)} of {total} stored postings "
          f"(min score {args.min_score}):\n")
    print(f"{'SCORE':>6}  {'SOURCE':<14}  {'TITLE':<42}  COMPANY")
    print("-" * 90)
    for r in rows:
        print(f"{r['score']:>6.1f}  {r['source']:<14}  "
              f"{_truncate(r['title'], 42):<42}  {_truncate(r['company'], 20)}")
    if args.verbose:
        print("\nLinks:")
        for r in rows:
            print(f"  [{r['score']:.0f}] {r['url']}")
    return 0


def cmd_sources(args) -> int:
    print("Available sources:")
    for name in available_source_names():
        print(f"  - {name}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gigradar",
        description="Monitor public job feeds, score gigs against your stack.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent(
            f"""\
            examples:
              python3 -m gigradar run
              python3 -m gigradar run --config config.toml
              python3 -m gigradar list --limit 15 --min-score 60 -v

            default db: {default_db_path()}
            """
        ),
    )
    parser.add_argument("--version", action="version",
                        version=f"GigRadar {__version__}")
    parser.add_argument("-c", "--config", default=None,
                        help="path to config.toml (defaults to built-in config)")
    parser.add_argument("--db", default=None,
                        help="path to SQLite db (defaults to user data dir)")

    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="fetch + score + store new postings")
    p_run.add_argument("--no-notify", action="store_true",
                       help="disable desktop notifications")
    p_run.set_defaults(func=cmd_run)

    p_list = sub.add_parser("list", help="show ranked stored postings")
    p_list.add_argument("-n", "--limit", type=int, default=20)
    p_list.add_argument("-m", "--min-score", type=float, default=0.0)
    p_list.add_argument("-v", "--verbose", action="store_true",
                        help="also print URLs")
    p_list.set_defaults(func=cmd_list)

    p_src = sub.add_parser("sources", help="list available sources")
    p_src.set_defaults(func=cmd_sources)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
