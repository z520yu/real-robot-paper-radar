from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from .store import StoredPaper


def build_markdown_report(
    papers: list[StoredPaper],
    days: int,
    zh_summaries: dict[str, str] | None = None,
    generated_at: datetime | None = None,
) -> str:
    generated_at = generated_at or datetime.now(UTC)
    zh_summaries = zh_summaries or {}
    lines = [
        "# Embodied Intelligence Weekly Radar",
        "",
        f"- Generated: {generated_at.strftime('%Y-%m-%d %H:%M UTC')}",
        f"- Window: last {days} days",
        f"- Paper count: {len(papers)}",
        "",
        "## How To Use",
        "",
        "1. Move must-read papers into Zotero `01_must_read`.",
        "2. Feed this file plus the summary prompt into Codex/OpenCode.",
        "3. Add the resulting ideas into Zotero `03_idea_pool` or your notes.",
        "",
        "## Candidate Papers",
        "",
    ]

    if not papers:
        lines.append("No papers matched the current filters.")
        return "\n".join(lines) + "\n"

    for idx, paper in enumerate(papers, start=1):
        terms = ", ".join(paper.matched_terms) if paper.matched_terms else "n/a"
        lines.extend(
            [
                f"### {idx}. {paper.title}",
                f"- Source: {paper.source_name}",
                f"- Published: {paper.published_at.strftime('%Y-%m-%d')}",
                f"- Score: {paper.score:.2f}",
                f"- Matched terms: {terms}",
                f"- URL: {paper.url}",
                f"- Summary (EN): {paper.summary[:500].strip()}",
                f"- 摘要 (ZH): {zh_summaries.get(paper.url, '未生成')}",
                "",
            ]
        )

    return "\n".join(lines) + "\n"


def write_report(report_dir: Path, content: str, stamp: datetime | None = None) -> Path:
    stamp = stamp or datetime.now(UTC)
    report_dir.mkdir(parents=True, exist_ok=True)
    path = report_dir / f"weekly-{stamp.strftime('%Y-%m-%d')}.md"
    path.write_text(content, encoding="utf-8")
    return path
