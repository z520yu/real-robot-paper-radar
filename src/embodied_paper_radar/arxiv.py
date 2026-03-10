from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from html import unescape
from html.parser import HTMLParser
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

from .config import FeedConfig


class _HTMLStripper(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        cleaned = data.strip()
        if cleaned:
            self.parts.append(cleaned)

    def text(self) -> str:
        return " ".join(self.parts)


@dataclass(slots=True)
class FeedItem:
    source: str
    source_name: str
    title: str
    url: str
    published_at: datetime
    summary: str


def fetch_feed(feed: FeedConfig, timeout_seconds: int = 20) -> list[FeedItem]:
    request = Request(
        feed.url,
        headers={"User-Agent": "embodied-paper-radar/0.1 (+https://arxiv.org)"},
    )
    with urlopen(request, timeout=timeout_seconds) as response:
        payload = response.read()

    root = ET.fromstring(payload)
    channel = root.find("channel")
    if channel is None:
        return []

    items: list[FeedItem] = []
    for item in channel.findall("item"):
        title = _text(item, "title")
        url = _text(item, "link")
        published_raw = _text(item, "pubDate")
        description = _text(item, "description")
        if not title or not url or not published_raw:
            continue

        published_at = parsedate_to_datetime(published_raw).astimezone(UTC)
        items.append(
            FeedItem(
                source=feed.url,
                source_name=feed.name,
                title=title,
                url=url,
                published_at=published_at,
                summary=_strip_html(description),
            )
        )
    return items


def _text(node: ET.Element, tag: str) -> str:
    child = node.find(tag)
    if child is None or child.text is None:
        return ""
    return child.text.strip()


def _strip_html(value: str) -> str:
    parser = _HTMLStripper()
    parser.feed(unescape(value))
    return parser.text()
