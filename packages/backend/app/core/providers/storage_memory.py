"""MemoryStorageProvider — in-process object store (dev / tests).

The sovereign default is MinIO; this is the no-dependency counterpart used in tests
and single-process dev (mirrors MemoryCache vs RedisCache). The backing store is
**class-level** on purpose: the API resolves a fresh provider instance per request,
so an upload and a later GET land on different instances yet must see the same bytes
(within one process). NOT for production / multi-replica — use MinIO there.
"""

from __future__ import annotations

from app.core.providers.base import StorageProvider


class MemoryStorageProvider(StorageProvider):
    code = "memory"

    # Process-global so instances share state across requests (dev/test only).
    _STORE: dict[str, bytes] = {}

    async def put(self, key: str, data: bytes, *, content_type: str = "") -> str:
        type(self)._STORE[key] = bytes(data)
        return f"mem://{key}"

    async def get(self, key: str) -> bytes:
        try:
            return type(self)._STORE[key]
        except KeyError as e:
            raise FileNotFoundError(key) from e

    async def delete(self, key: str) -> None:
        type(self)._STORE.pop(key, None)

    async def ensure_bucket(self, bucket: str) -> None:
        # No bucket concept in the flat in-memory store — trivially satisfied.
        return None

    async def healthcheck(self) -> dict:
        return {"ok": True, "detail": f"{len(type(self)._STORE)} object(s) in memory"}
