"""Stream ingest with two sources and a pluggable transport.

* ``replay`` — stream a bundled CSV of saved headlines (no keys, deterministic).
* ``rss``    — pull live headlines from one or more RSS feeds.

Transport is Redis Streams when ``REDIS_URL`` is set, otherwise an in-process
queue so the demo runs with zero infrastructure.
"""

from __future__ import annotations

import csv
import logging
import time
from collections import deque
from collections.abc import Iterator
from pathlib import Path

from .config import Settings, get_settings
from .schemas import Headline

logger = logging.getLogger("signaldesk.ingest")

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def read_replay_csv(path: Path | None = None) -> list[Headline]:
    """Load the bundled sample headlines for replay mode."""
    path = path or (DATA_DIR / "sample_headlines.csv")
    out: list[Headline] = []
    with path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            out.append(
                Headline(
                    id=row["id"],
                    text=row["text"],
                    source=row.get("source", "replay"),
                )
            )
    return out


def replay_stream(delay_s: float = 0.0, path: Path | None = None) -> Iterator[Headline]:
    """Yield bundled headlines, optionally pacing them like a live feed."""
    for h in read_replay_csv(path):
        yield h
        if delay_s:
            time.sleep(delay_s)


def rss_stream(settings: Settings | None = None) -> Iterator[Headline]:
    """Yield headlines from configured RSS feeds (best-effort)."""
    import feedparser  # local import; only needed for live mode

    s = settings or get_settings()
    seen: set[str] = set()
    for url in s.rss_feeds:
        feed = feedparser.parse(url)
        for entry in feed.entries:
            hid = getattr(entry, "id", None) or getattr(entry, "link", entry.title)
            if hid in seen:
                continue
            seen.add(hid)
            yield Headline(id=str(hid), text=entry.title, source=url)


class InMemoryStream:
    """A tiny stand-in for Redis Streams used when no broker is configured."""

    def __init__(self) -> None:
        self._q: deque[Headline] = deque()

    def publish(self, h: Headline) -> None:
        self._q.append(h)

    def consume(self) -> Iterator[Headline]:
        while self._q:
            yield self._q.popleft()


def get_stream(settings: Settings | None = None):
    """Return a Redis-backed stream wrapper, or an in-memory one."""
    s = settings or get_settings()
    if not s.redis_url:
        return InMemoryStream()
    from .redis_stream import RedisStream  # optional dependency path

    return RedisStream(s.redis_url, s.stream_key)
