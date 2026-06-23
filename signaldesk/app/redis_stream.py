"""Redis Streams transport (optional; used only when REDIS_URL is set)."""

from __future__ import annotations

import json
from collections.abc import Iterator

from .schemas import Headline


class RedisStream:
    """Thin wrapper around a Redis Stream for headline fan-out."""

    def __init__(self, url: str, key: str) -> None:
        import redis  # local import keeps base install light

        self._r = redis.from_url(url, decode_responses=True)
        self._key = key
        self._last = "0-0"

    def publish(self, h: Headline) -> None:
        self._r.xadd(
            self._key,
            {"id": h.id, "text": h.text, "source": h.source},
        )

    def consume(self, block_ms: int = 1000) -> Iterator[Headline]:
        resp = self._r.xread({self._key: self._last}, block=block_ms, count=50)
        for _key, entries in resp or []:
            for entry_id, fields in entries:
                self._last = entry_id
                yield Headline(
                    id=fields["id"], text=fields["text"], source=fields.get("source", "redis")
                )

    def __len__(self) -> int:  # pragma: no cover - convenience only
        return int(self._r.xlen(self._key))

    def _dump(self, h: Headline) -> str:  # pragma: no cover
        return json.dumps(h.model_dump(mode="json"))
