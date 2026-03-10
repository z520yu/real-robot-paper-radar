from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from http.client import IncompleteRead
import json
from pathlib import Path
import re
from urllib.error import HTTPError, URLError
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
) -> dict[str, str]:
    if not config.enabled:
        return {}

    cache = TranslationCache.load(config.cache_path)
    outputs: dict[str, str] = {}

    for paper in papers:
        source_text = paper.summary.strip()
        if not source_text:
            continue
        cache_key = _cache_key(config, paper.url, source_text)
        cached = cache.get(cache_key)
        if cached:
            outputs[paper.url] = cached
            continue

        try:
            translated = translate_text(source_text, config)
        except (HTTPError, URLError, TimeoutError, IncompleteRead, ValueError):
            translated = ""
        if translated:
            outputs[paper.url] = translated
            cache.set(cache_key, translated)

    cache.save()
    return outputs


def translate_text(text: str, config: TranslationConfig) -> str:
    chunks = _split_text(text, max_chars=_max_chunk_chars(config))
    translated_chunks: list[str] = []
    for chunk in chunks:
        translated = _translate_chunk(chunk, config)
        if translated:
            translated_chunks.append(translated.strip())
    return " ".join(part for part in translated_chunks if part).strip()


def _max_chunk_chars(config: TranslationConfig) -> int:
    if config.backend == "mymemory":
        return 350
    if config.backend == "googlefree":
        return 1200
    if config.backend == "libretranslate":
        return 1200
    return 500


def _translate_chunk(text: str, config: TranslationConfig) -> str:
    if config.backend == "mymemory":
        try:
            return _translate_mymemory(text, config)
        except HTTPError as exc:
            if exc.code != 429:
                raise
            return _translate_googlefree(text, config)
    if config.backend == "googlefree":
        return _translate_googlefree(text, config)
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


def _translate_googlefree(text: str, config: TranslationConfig) -> str:
    query = quote(text)
    source = quote(config.source_lang)
    target = quote(config.target_lang)
    url = (
        "https://translate.googleapis.com/translate_a/single"
        f"?client=gtx&sl={source}&tl={target}&dt=t&q={query}"
    )
    request = Request(url, headers={"User-Agent": "embodied-paper-radar/0.1"})
    with urlopen(request, timeout=config.timeout_seconds) as response:
        payload = json.loads(response.read().decode("utf-8"))
    segments = payload[0] if isinstance(payload, list) and payload else []
    return "".join(
        part[0] for part in segments if isinstance(part, list) and part and isinstance(part[0], str)
    ).strip()


def _cache_key(config: TranslationConfig, url: str, text: str) -> str:
    raw = f"{config.backend}|{config.endpoint}|{config.source_lang}|{config.target_lang}|{url}|{text}"
    return sha256(raw.encode("utf-8")).hexdigest()


def _split_text(text: str, max_chars: int) -> list[str]:
    cleaned = " ".join(text.split())
    if len(cleaned) <= max_chars:
        return [cleaned]

    sentences = re.split(r"(?<=[.!?])\s+", cleaned)
    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        if len(sentence) > max_chars:
            chunks.extend(_split_long_sentence(sentence, max_chars))
            continue
        candidate = sentence if not current else f"{current} {sentence}"
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                chunks.append(current)
            current = sentence
    if current:
        chunks.append(current)
    return chunks


def _split_long_sentence(text: str, max_chars: int) -> list[str]:
    words = text.split()
    chunks: list[str] = []
    current = ""
    for word in words:
        candidate = word if not current else f"{current} {word}"
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                chunks.append(current)
            current = word
    if current:
        chunks.append(current)
    return chunks
