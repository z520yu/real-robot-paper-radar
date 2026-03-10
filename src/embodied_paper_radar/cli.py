from __future__ import annotations

import argparse
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path

from .arxiv import FeedItem, fetch_feed
from .codex_screen import build_screen_markdown, run_codex_screen
from .config import RadarConfig, load_config
from .report import build_markdown_report, write_report
from .ris import build_ris_export, write_ris_export, write_screened_ris_exports
from .store import connect, recent_papers, upsert_paper
from .translation import translate_paper_summaries


def main() -> int:
    parser = argparse.ArgumentParser(description="Embodied intelligence paper radar")
    parser.add_argument(
        "--config",
        default="config/example_config.toml",
        help="Path to the radar config TOML file.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    fetch_parser = subparsers.add_parser("fetch", help="Fetch papers into the local database")
    fetch_parser.add_argument("--limit-per-feed", type=int, default=25)

    report_parser = subparsers.add_parser("report", help="Generate a markdown report")
    report_parser.add_argument("--days", type=int, default=None)
    report_parser.add_argument("--limit", type=int, default=None)

    ris_parser = subparsers.add_parser("export-ris", help="Export recent papers as a Zotero-importable RIS file")
    ris_parser.add_argument("--days", type=int, default=None)
    ris_parser.add_argument("--limit", type=int, default=None)
    ris_parser.add_argument("--output", default=None, help="Output .ris path. Defaults to reports/weekly-YYYY-MM-DD.ris")

    codex_parser = subparsers.add_parser("screen-codex", help="Use codex exec to classify recent papers")
    codex_parser.add_argument("--days", type=int, default=None)
    codex_parser.add_argument("--limit", type=int, default=None)
    codex_parser.add_argument("--model", default=None, help="Optional Codex model override")

    weekly_parser = subparsers.add_parser("weekly", help="Run fetch, report, codex screening, and RIS export in one command")
    weekly_parser.add_argument("--limit-per-feed", type=int, default=25)
    weekly_parser.add_argument("--days", type=int, default=None)
    weekly_parser.add_argument("--limit", type=int, default=None)
    weekly_parser.add_argument("--model", default=None, help="Optional Codex model override")
    weekly_parser.add_argument("--skip-codex", action="store_true", help="Skip the Codex screening step")
    weekly_parser.add_argument("--skip-ris", action="store_true", help="Skip RIS export")

    args = parser.parse_args()
    config = load_config(args.config)

    if args.command == "fetch":
        return _run_fetch(config, args.limit_per_feed)
    if args.command == "report":
        return _run_report(config, days=args.days, limit=args.limit)
    if args.command == "export-ris":
        return _run_export_ris(config, days=args.days, limit=args.limit, output=args.output)
    if args.command == "screen-codex":
        return _run_screen_codex(config, days=args.days, limit=args.limit, model=args.model)
    if args.command == "weekly":
        return _run_weekly(
            config,
            limit_per_feed=args.limit_per_feed,
            days=args.days,
            limit=args.limit,
            model=args.model,
            skip_codex=args.skip_codex,
            skip_ris=args.skip_ris,
        )
    parser.error(f"Unknown command: {args.command}")
    return 2


def _run_fetch(config: RadarConfig, limit_per_feed: int) -> int:
    conn = connect(config.database_path)
    inserted = 0
    kept = 0
    skipped = 0
    try:
        for feed in config.feeds:
            items = fetch_feed(feed)[:limit_per_feed]
            for item in items:
                score, matched_terms = rank_item(
                    item,
                    term_weights=config.term_weights,
                    exclude_terms=config.exclude_terms,
                    feed_weight=feed.weight,
                )
                if score < config.min_score:
                    skipped += 1
                    continue
                kept += 1
                if upsert_paper(conn, item, score, matched_terms):
                    inserted += 1
        conn.commit()
    finally:
        conn.close()

    print(f"kept={kept} inserted_or_updated={inserted} skipped={skipped}")
    return 0


def _run_report(config: RadarConfig, days: int | None, limit: int | None) -> int:
    conn = connect(config.database_path)
    try:
        papers = recent_papers(
            conn,
            days=days or config.report_days,
            limit=limit or config.report_limit,
        )
    finally:
        conn.close()

    zh_summaries = translate_paper_summaries(papers, config.translation)
    content = build_markdown_report(
        papers,
        days=days or config.report_days,
        zh_summaries=zh_summaries,
    )
    output_path = write_report(config.report_dir, content)
    print(output_path)
    return 0


def _run_export_ris(
    config: RadarConfig,
    days: int | None,
    limit: int | None,
    output: str | None,
) -> int:
    conn = connect(config.database_path)
    try:
        papers = recent_papers(
            conn,
            days=days or config.report_days,
            limit=limit or config.report_limit,
        )
    finally:
        conn.close()

    content = build_ris_export(papers)
    output_path = write_ris_export(config.report_dir, content, output_path=Path(output).expanduser() if output else None)
    print(output_path)
    return 0


def _run_screen_codex(
    config: RadarConfig,
    days: int | None,
    limit: int | None,
    model: str | None,
) -> int:
    conn = connect(config.database_path)
    try:
        papers = recent_papers(
            conn,
            days=days or config.report_days,
            limit=limit or config.report_limit,
        )
    finally:
        conn.close()

    if not papers:
        print("No papers available to screen.")
        return 0

    output_path = run_codex_screen(
        papers=papers,
        prompt_path=config.prompt_dir / "codex_screen_prompt.md",
        schema_path=config.prompt_dir / "codex_screen_schema.json",
        output_dir=config.report_dir,
        working_dir=Path.cwd(),
        model=model,
    )
    markdown_path = build_screen_markdown(output_path, config.report_dir)
    print(output_path)
    print(markdown_path)
    return 0


def _run_weekly(
    config: RadarConfig,
    limit_per_feed: int,
    days: int | None,
    limit: int | None,
    model: str | None,
    skip_codex: bool,
    skip_ris: bool,
) -> int:
    days = days or config.report_days
    limit = limit or config.report_limit

    print("[1/4] Fetching fresh papers...")
    fetch_code = _run_fetch(config, limit_per_feed=limit_per_feed)
    if fetch_code != 0:
        return fetch_code

    if skip_codex:
        print("[2/4] Skipping Codex screening.")
    else:
        print("[2/4] Running Codex screening...")
        codex_code = _run_screen_codex(config, days=days, limit=limit, model=model)
        if codex_code != 0:
            return codex_code

    print("[3/4] Building weekly markdown report...")
    report_code = _run_report(config, days=days, limit=limit)
    if report_code != 0:
        return report_code

    if skip_ris:
        print("[4/4] Skipping RIS export.")
    else:
        print("[4/4] Exporting RIS for Zotero...")
        ris_code = _run_export_ris(config, days=days, limit=limit, output=None)
        if ris_code != 0:
            return ris_code
        if not skip_codex:
            screened_ris_code = _run_export_screened_ris(config, days=days, limit=limit)
            if screened_ris_code != 0:
                return screened_ris_code

    print("Weekly pipeline finished.")
    return 0


def _run_export_screened_ris(
    config: RadarConfig,
    days: int | None,
    limit: int | None,
) -> int:
    conn = connect(config.database_path)
    try:
        papers = recent_papers(
            conn,
            days=days or config.report_days,
            limit=limit or config.report_limit,
        )
    finally:
        conn.close()

    screen_json_path = config.report_dir / f"screen-{datetime.now(UTC).strftime('%Y-%m-%d')}.json"
    if not screen_json_path.exists():
        print("No screen JSON found for filtered RIS export.")
        return 0

    paths = write_screened_ris_exports(config.report_dir, papers, screen_json_path)
    for path in paths:
        print(path)
    return 0


def rank_item(
    item: FeedItem,
    term_weights: dict[str, float],
    exclude_terms: Iterable[str],
    feed_weight: float,
) -> tuple[float, list[str]]:
    haystack = f"{item.title}\n{item.summary}".lower()
    for term in exclude_terms:
        if term.lower() in haystack:
            return 0.0, []

    matched_terms: list[str] = []
    score = 0.0
    for term, weight in term_weights.items():
        if term.lower() in haystack:
            matched_terms.append(term)
            score += weight

    score *= max(feed_weight, 0.1)
    score += _recency_bonus(item.published_at)
    return round(score, 2), matched_terms


def _recency_bonus(published_at: datetime) -> float:
    age_days = max((datetime.now(UTC) - published_at.astimezone(UTC)).days, 0)
    if age_days <= 3:
        return 1.5
    if age_days <= 7:
        return 1.0
    if age_days <= 14:
        return 0.5
    return 0.0
