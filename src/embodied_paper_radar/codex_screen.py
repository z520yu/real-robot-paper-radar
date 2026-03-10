from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
import json
from pathlib import Path
import subprocess

from .store import StoredPaper


def run_codex_screen(
    papers: list[StoredPaper],
    prompt_path: Path,
    schema_path: Path,
    output_dir: Path,
    working_dir: Path,
    model: str | None = None,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y-%m-%d")
    output_path = output_dir / f"screen-{stamp}.json"
    payload = _build_payload(papers, prompt_path)

    command = [
        "codex",
        "exec",
        "--skip-git-repo-check",
        "--sandbox",
        "read-only",
        "--output-schema",
        str(schema_path),
        "-o",
        str(output_path),
        "-C",
        str(working_dir),
        "-",
    ]
    if model:
        command[2:2] = ["--model", model]

    subprocess.run(
        command,
        input=payload,
        text=True,
        check=True,
    )
    return output_path


def build_screen_markdown(screen_json_path: Path, output_dir: Path) -> Path:
    data = json.loads(screen_json_path.read_text(encoding="utf-8"))
    stamp = datetime.now(UTC).strftime("%Y-%m-%d")
    output_path = output_dir / f"screen-{stamp}.md"

    lines = [
        "# Codex Screening Results",
        "",
        "## Decisions",
        "",
    ]
    for paper in data["papers"]:
        lines.extend(
            [
                f"### {paper['title']}",
                f"- Decision: {paper['decision']}",
                f"- Real-robot signal: {paper['real_robot_signal']}",
                f"- Novelty signal: {paper['novelty_signal']}",
                f"- URL: {paper['url']}",
                f"- Quick reason: {paper['reason']}",
                f"- Relevance: {paper['relevance']}",
                f"- Missing evidence: {paper['evidence_gap']}",
                f"- Action: {paper['recommended_action']}",
                "",
            ]
        )

    lines.extend(["## Summary", ""])
    lines.append(f"- Read now: {', '.join(data['summary']['read_now_titles']) or 'None'}")
    lines.append("")
    lines.append("### Common Patterns")
    for item in data["summary"]["common_patterns"]:
        lines.append(f"- {item}")
    lines.append("")
    lines.append("### Research Gaps")
    for item in data["summary"]["research_gaps"]:
        lines.append(f"- {item}")
    lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path


def _build_payload(papers: list[StoredPaper], prompt_path: Path) -> str:
    prompt = prompt_path.read_text(encoding="utf-8").strip()
    items = []
    for paper in papers:
        items.append(
            {
                "title": paper.title,
                "url": paper.url,
                "source_name": paper.source_name,
                "published_at": paper.published_at.astimezone(UTC).isoformat(),
                "score": paper.score,
                "matched_terms": paper.matched_terms,
                "summary": paper.summary,
            }
        )
    return f"{prompt}\n\nCandidate papers JSON:\n{json.dumps(items, ensure_ascii=False, indent=2)}\n"
