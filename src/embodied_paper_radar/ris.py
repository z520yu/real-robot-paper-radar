from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path

from .store import StoredPaper


def build_ris_export(papers: list[StoredPaper]) -> str:
    lines: list[str] = []
    for paper in papers:
        date = paper.published_at.astimezone(UTC).strftime("%Y/%m/%d")
        year = paper.published_at.astimezone(UTC).strftime("%Y")
        notes = [
            f"Radar source: {paper.source_name}",
            f"Radar score: {paper.score:.2f}",
        ]
        if paper.matched_terms:
            notes.append(f"Matched terms: {', '.join(paper.matched_terms)}")

        lines.extend(
            [
                "TY  - JOUR",
                f"T1  - {_clean(paper.title)}",
                "JO  - arXiv",
                f"PY  - {year}",
                f"DA  - {date}",
                f"UR  - {_clean(paper.url)}",
                f"N2  - {_clean(paper.summary)}",
            ]
        )
        for note in notes:
            lines.append(f"N1  - {_clean(note)}")
        lines.append("ER  - ")
        lines.append("")

    return "\n".join(lines)


def write_ris_export(
    report_dir: Path,
    content: str,
    output_path: Path | None = None,
    stamp: datetime | None = None,
) -> Path:
    stamp = stamp or datetime.now(UTC)
    output_path = output_path or (report_dir / f"weekly-{stamp.strftime('%Y-%m-%d')}.ris")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    return output_path


def write_screened_ris_exports(
    report_dir: Path,
    papers: list[StoredPaper],
    screen_json_path: Path,
    stamp: datetime | None = None,
) -> list[Path]:
    stamp = stamp or datetime.now(UTC)
    decisions = _load_decisions(screen_json_path)
    buckets: dict[str, list[StoredPaper]] = {
        "read_now": [],
        "read_later": [],
    }

    for paper in papers:
        decision = decisions.get(paper.url)
        if decision in buckets:
            buckets[decision].append(paper)

    outputs: list[Path] = []
    for decision, items in buckets.items():
        if not items:
            continue
        content = build_ris_export(items)
        path = report_dir / f"{decision}-{stamp.strftime('%Y-%m-%d')}.ris"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        outputs.append(path)
    return outputs


def _load_decisions(screen_json_path: Path) -> dict[str, str]:
    data = json.loads(screen_json_path.read_text(encoding="utf-8"))
    decisions: dict[str, str] = {}
    for item in data.get("papers", []):
        url = item.get("url")
        decision = item.get("decision")
        if isinstance(url, str) and isinstance(decision, str):
            decisions[url] = decision
    return decisions


def _clean(value: str) -> str:
    return " ".join(value.replace("\r", " ").replace("\n", " ").split())
