from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
import sqlite3

from .arxiv import FeedItem


@dataclass(slots=True)
class StoredPaper:
    title: str
    url: str
    source_name: str
    published_at: datetime
    score: float
    matched_terms: list[str]
    summary: str


SCHEMA = """
CREATE TABLE IF NOT EXISTS papers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    source TEXT NOT NULL,
    source_name TEXT NOT NULL,
    published_at TEXT NOT NULL,
    summary TEXT NOT NULL,
    score REAL NOT NULL,
    matched_terms TEXT NOT NULL,
    inserted_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_papers_published_at ON papers(published_at DESC);
CREATE INDEX IF NOT EXISTS idx_papers_score ON papers(score DESC);
"""


def connect(database_path: Path) -> sqlite3.Connection:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(database_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA)
    return conn


def upsert_paper(
    conn: sqlite3.Connection,
    item: FeedItem,
    score: float,
    matched_terms: list[str],
) -> bool:
    inserted_at = datetime.now(UTC).isoformat()
    cursor = conn.execute(
        """
        INSERT INTO papers (url, title, source, source_name, published_at, summary, score, matched_terms, inserted_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(url) DO UPDATE SET
            title = excluded.title,
            source = excluded.source,
            source_name = excluded.source_name,
            published_at = excluded.published_at,
            summary = excluded.summary,
            score = excluded.score,
            matched_terms = excluded.matched_terms
        """,
        (
            item.url,
            item.title,
            item.source,
            item.source_name,
            item.published_at.isoformat(),
            item.summary,
            score,
            ",".join(matched_terms),
            inserted_at,
        ),
    )
    return cursor.rowcount > 0


def recent_papers(
    conn: sqlite3.Connection,
    days: int,
    limit: int,
) -> list[StoredPaper]:
    since = (datetime.now(UTC) - timedelta(days=days)).isoformat()
    cursor = conn.execute(
        """
        SELECT title, url, source_name, published_at, score, matched_terms, summary
        FROM papers
        WHERE inserted_at >= ?
        ORDER BY score DESC, published_at DESC
        LIMIT ?
        """,
        (since, limit),
    )
    rows = cursor.fetchall()
    papers: list[StoredPaper] = []
    for row in rows:
        papers.append(
            StoredPaper(
                title=row[0],
                url=row[1],
                source_name=row[2],
                published_at=datetime.fromisoformat(row[3]).astimezone(UTC),
                score=float(row[4]),
                matched_terms=[term for term in row[5].split(",") if term],
                summary=row[6],
            )
        )
    return papers
