"""F2 — MinIO provider fails loud on missing creds (no opaque boto3 403 later)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.providers.storage_minio import MinIOStorageProvider  # noqa: E402


def test_missing_creds_raise_clear_error(monkeypatch):
    monkeypatch.delenv("MINIO_ACCESS_KEY", raising=False)
    monkeypatch.delenv("MINIO_SECRET_KEY", raising=False)
    p = MinIOStorageProvider({"endpoint": "http://minio:9000", "bucket": "b"})
    with pytest.raises(RuntimeError, match="MinIO"):
        p._s3()


def test_creds_via_config_build_a_client(monkeypatch):
    monkeypatch.delenv("MINIO_ACCESS_KEY", raising=False)
    monkeypatch.delenv("MINIO_SECRET_KEY", raising=False)
    p = MinIOStorageProvider({"endpoint": "http://minio:9000", "bucket": "b",
                              "access_key": "ak", "secret_key": "sk"})
    assert p._s3() is not None  # creds present (injectable) => client builds, no raise
