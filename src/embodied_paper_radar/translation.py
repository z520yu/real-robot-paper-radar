from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

from .config import TranslationConfig
from .store import StoredPaper


@dataclass(slots=True)
class TranslationCache:
    path: Path
    data: dict[str, str]

    @classmethod
    def load(cls, path: Path) -> "TranslationCache":
        if path.exists():
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(payload, dict):
                    return cls(path=path, data={str(k): str(v) for k, v in payload.items()})
            except json.JSONDecodeError:
                pass
        return cls(path=path, data={})

    def get(self, key: str) -> str | None:
        return self.data.get(key)

    def set(self, key: str, value: str) -> None:
        self.data[key] = value

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self.data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def translate_paper_summaries(
    papers: list[StoredPaper],
    config: TranslationConfig,
    max_chars: int = 500,
) -> dict[str, str]:
    if not config.enabled:
        return {}

    cache = TranslationCache.load(config.cache_path)
    outputs: dict[str, str] = {}

    for paper in papers:
        source_text = paper.summary[:max_chars].strip()
        if not source_text:
            continue
        cache_key = _cache_key(config, paper.url, source_text)
        cached = cache.get(cache_key)
        if cached:
            outputs[paper.url] = cached
            continue

        translated = translate_text(source_text, config)
        if translated:
            outputs[paper.url] = translated
            cache.set(cache_key, translated)

    cache.save()
    return outputs


def translate_text(text: str, config: TranslationConfig) -> str:
    if config.backend == "mymemory":
        return _translate_mymemory(text, config)
    if config.backend == "libretranslate":
        return _translate_libretranslate(text, config)
    raise ValueError(f"Unsupported translation backend: {config.backend}")


def _translate_mymemory(text: str, config: TranslationConfig) -> str:
    endpoint = config.endpoint or "https://api.mymemory.translated.net/get"
    query = quote(text)
    langpair = quote(f"{config.source_lang}|{config.target_lang}")
    url = f"{endpoint}?q={query}&langpair={langpair}"
    request = Request(url, headers={"User-Agent": "embodied-paper-radar/0.1"})
    with urlopen(request, timeout=config.timeout_seconds) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return str(payload.get("responseData", {}).get("translatedText", "")).strip()


def _translate_libretranslate(text: str, config: TranslationConfig) -> str:
    if not config.endpoint:
        raise ValueError("LibreTranslate backend requires an endpoint in the config.")
    payload = json.dumps(
        {
            "q": text,
            "source": config.source_lang,
            "target": config.target_lang,
            "format": "text",
        }
    ).encode("utf-8")
    request = Request(
        config.endpoint,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "embodied-paper-radar/0.1",
        },
        method="POST",
    )
    with urlopen(request, timeout=config.timeout_seconds) as response:
        data = json.loads(response.read().decode("utf-8"))
    return str(data.get("translatedText", "")).strip()


def _cache_key(config: TranslationConfig, url: str, text: str) -> str:
    raw = f"{config.backend}|{config.endpoint}|{config.source_lang}|{config.target_lang}|{url}|{text}"
    return sha256(raw.encode("utf-8")).hexdigest()
