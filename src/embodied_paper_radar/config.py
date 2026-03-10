from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tomllib


@dataclass(slots=True)
class FeedConfig:
    name: str
    url: str
    weight: float = 1.0


@dataclass(slots=True)
class TranslationConfig:
    enabled: bool
    backend: str
    endpoint: str | None
    source_lang: str
    target_lang: str
    timeout_seconds: int
    cache_path: Path


@dataclass(slots=True)
class RadarConfig:
    database_path: Path
    report_dir: Path
    prompt_dir: Path
    translation: TranslationConfig
    feeds: list[FeedConfig]
    term_weights: dict[str, float]
    exclude_terms: list[str]
    min_score: float = 1.0
    report_days: int = 7
    report_limit: int = 20


def load_config(config_path: str | Path) -> RadarConfig:
    path = Path(config_path).expanduser().resolve()
    data = tomllib.loads(path.read_text(encoding="utf-8"))

    database_path = _resolve_path(path, data["database"]["path"])
    report_dir = _resolve_path(path, data["report"]["dir"])
    prompt_dir = _resolve_path(path, data["prompt"]["dir"])
    translation_data = data.get("translation", {})
    translation = TranslationConfig(
        enabled=bool(translation_data.get("enabled", True)),
        backend=str(translation_data.get("backend", "mymemory")),
        endpoint=str(translation_data["endpoint"]) if translation_data.get("endpoint") else None,
        source_lang=str(translation_data.get("source_lang", "en")),
        target_lang=str(translation_data.get("target_lang", "zh-CN")),
        timeout_seconds=int(translation_data.get("timeout_seconds", 20)),
        cache_path=_resolve_path(path, translation_data.get("cache_path", "../data/translation_cache.json")),
    )
    feeds = [FeedConfig(**feed) for feed in data["feeds"]]

    filters = data["filters"]
    report = data["report"]
    include_terms = list(filters.get("include_terms", []))
    weighted_terms = {
        key: float(value) for key, value in filters.get("term_weights", {}).items()
    }
    for term in include_terms:
        weighted_terms.setdefault(term, 1.0)
    return RadarConfig(
        database_path=database_path,
        report_dir=report_dir,
        prompt_dir=prompt_dir,
        translation=translation,
        feeds=feeds,
        term_weights=weighted_terms,
        exclude_terms=list(filters.get("exclude_terms", [])),
        min_score=float(filters.get("min_score", 1.0)),
        report_days=int(report.get("days", 7)),
        report_limit=int(report.get("limit", 20)),
    )


def _resolve_path(config_path: Path, raw_path: str) -> Path:
    candidate = Path(raw_path).expanduser()
    if candidate.is_absolute():
        return candidate
    return (config_path.parent / candidate).resolve()
