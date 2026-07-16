"""Phase 1bis — StorageProvider.ensure_bucket across all storage backends.

Dynamic agility: a module declares required_buckets; the reconciler asks the
*active* storage provider to create them (idempotent). Each concrete provider
implements it against its own backend; the base raises NotImplementedError so an
unsupporting provider is handled explicitly (not silently).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from botocore.exceptions import ClientError

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.providers.storage_memory import MemoryStorageProvider  # noqa: E402
from app.core.providers.storage_minio import MinIOStorageProvider  # noqa: E402
from app.core.providers.storage_s3 import S3StorageProvider  # noqa: E402


class _FakeS3:
    """Records create_bucket; head_bucket 404s for unknown buckets (like boto3)."""

    def __init__(self, existing=()):
        self.existing = set(existing)
        self.created: list[dict] = []

    def head_bucket(self, Bucket):  # noqa: N803 (boto3 kwarg name)
        if Bucket not in self.existing:
            raise ClientError({"Error": {"Code": "404"}}, "HeadBucket")

    def create_bucket(self, **kw):
        self.created.append(kw)
        self.existing.add(kw["Bucket"])


@pytest.mark.asyncio
async def test_memory_ensure_bucket_is_noop():
    # In-memory has no bucket concept — ensure_bucket trivially succeeds so the
    # reconciler treats memory as "bucket satisfied".
    await MemoryStorageProvider().ensure_bucket("anything")  # no raise


@pytest.mark.asyncio
async def test_minio_creates_bucket_when_absent():
    p = MinIOStorageProvider({"bucket": "docs"})
    p._client = _FakeS3()  # inject: bucket does not exist yet
    await p.ensure_bucket("invoices")
    assert [c["Bucket"] for c in p._client.created] == ["invoices"]


@pytest.mark.asyncio
async def test_minio_is_idempotent_when_bucket_present():
    p = MinIOStorageProvider({"bucket": "docs"})
    p._client = _FakeS3(existing={"invoices"})
    await p.ensure_bucket("invoices")
    assert p._client.created == []  # already there → no create


@pytest.mark.asyncio
async def test_s3_creates_with_location_constraint_off_us_east_1():
    p = S3StorageProvider({"bucket": "docs", "region": "eu-west-1"})
    p._client = _FakeS3()
    await p.ensure_bucket("invoices")
    assert p._client.created[0]["Bucket"] == "invoices"
    assert p._client.created[0]["CreateBucketConfiguration"] == {
        "LocationConstraint": "eu-west-1"}


@pytest.mark.asyncio
async def test_s3_no_location_constraint_in_us_east_1():
    p = S3StorageProvider({"bucket": "docs", "region": "us-east-1"})
    p._client = _FakeS3()
    await p.ensure_bucket("invoices")
    assert "CreateBucketConfiguration" not in p._client.created[0]


class _RaceS3(_FakeS3):
    """head_bucket 404 (absent) but create_bucket loses the race to another replica."""
    def create_bucket(self, **kw):
        raise ClientError({"Error": {"Code": "BucketAlreadyOwnedByYou"}}, "CreateBucket")


@pytest.mark.asyncio
async def test_minio_tolerates_concurrent_create_race():
    # 100+ agents / multi-replica boot : two backends head_bucket->404 then race on
    # create_bucket ; the loser gets BucketAlreadyOwnedByYou. Idempotent success, not error.
    p = MinIOStorageProvider({"bucket": "docs"})
    p._client = _RaceS3()
    await p.ensure_bucket("invoices")   # must NOT raise


@pytest.mark.asyncio
async def test_s3_tolerates_concurrent_create_race():
    p = S3StorageProvider({"bucket": "docs", "region": "eu-west-1"})
    p._client = _RaceS3()
    await p.ensure_bucket("invoices")   # must NOT raise


@pytest.mark.asyncio
async def test_base_default_is_not_supported():
    # A provider that doesn't back a bucketed store must fail explicitly, letting
    # the reconciler surface it — never a silent success.
    from app.core.providers.base import StorageProvider

    class _Bare(StorageProvider):
        code = "bare"
        async def put(self, key, data, *, content_type=""): ...
        async def get(self, key): ...
        async def delete(self, key): ...

    with pytest.raises(NotImplementedError):
        await _Bare().ensure_bucket("x")
