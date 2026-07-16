"""MinIOStorageProvider — S3 object storage via the scoped service account.

Sovereign storage provider. Endpoint/bucket come from the DB config or the
rendered env (MINIO_ENDPOINT/MINIO_BUCKET); the scoped SA creds come from the
env the deploy layer renders (MINIO_ACCESS_KEY/MINIO_SECRET_KEY). boto3 (sync)
is wrapped in asyncio.to_thread so the async API is non-blocking. Path-style
addressing is required for MinIO.
"""

from __future__ import annotations

import asyncio
import os

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from app.core.providers.base import StorageProvider, cfg

_ABSENT_BUCKET_CODES = {"404", "NoSuchBucket", "NotFound"}
# Course multi-replica : head_bucket->404 sur deux replicas, le 2e create_bucket perd
# la course -> deja possede = succes idempotent, pas une erreur.
_ALREADY_OWNED_CODES = {"BucketAlreadyOwnedByYou", "BucketAlreadyExists"}


class MinIOStorageProvider(StorageProvider):
    code = "minio"

    @classmethod
    def config_schema(cls):
        # Credentials (access_key/secret_key) travel via secret_ref/env — not here.
        return [
            cfg("endpoint", "Endpoint", hint="http://minio:9000"),
            cfg("bucket", "Bucket", hint="facil-documents"),
        ]

    def __init__(self, config=None) -> None:
        super().__init__(config)
        self._endpoint = (self.config.get("endpoint")
                          or os.environ.get("MINIO_ENDPOINT", "http://minio:9000"))
        self._bucket = (self.config.get("bucket")
                        or os.environ.get("MINIO_BUCKET", "facil-documents"))
        # Creds: injectable via config (a future consumer can pass vault-resolved
        # values) else the env the deploy layer renders / the vault hydrates (S2).
        self._access = self.config.get("access_key") or os.environ.get("MINIO_ACCESS_KEY", "")
        self._secret = self.config.get("secret_key") or os.environ.get("MINIO_SECRET_KEY", "")
        self._client = None

    def _s3(self):
        if self._client is None:
            # Fail loud on absent creds rather than let boto3 surface an opaque
            # 403 SignatureDoesNotMatch only at the first put/get (F2).
            if not self._access or not self._secret:
                raise RuntimeError(
                    "MinIO credentials are missing (MINIO_ACCESS_KEY/MINIO_SECRET_KEY "
                    "empty) — refusing to build the S3 client. Ensure the deploy layer "
                    "rendered the scoped SA creds (or the vault hydrated them).")
            self._client = boto3.client(
                "s3", endpoint_url=self._endpoint,
                aws_access_key_id=self._access, aws_secret_access_key=self._secret,
                region_name="us-east-1",
                config=Config(s3={"addressing_style": "path"}))
        return self._client

    async def put(self, key: str, data: bytes, *, content_type: str = "") -> str:
        def _put() -> str:
            kw = {"Bucket": self._bucket, "Key": key, "Body": data}
            if content_type:
                kw["ContentType"] = content_type
            self._s3().put_object(**kw)
            return f"s3://{self._bucket}/{key}"
        return await asyncio.to_thread(_put)

    async def get(self, key: str) -> bytes:
        def _get() -> bytes:
            return self._s3().get_object(Bucket=self._bucket, Key=key)["Body"].read()
        return await asyncio.to_thread(_get)

    async def delete(self, key: str) -> None:
        def _del() -> None:
            self._s3().delete_object(Bucket=self._bucket, Key=key)
        await asyncio.to_thread(_del)

    async def ensure_bucket(self, bucket: str) -> None:
        def _ensure() -> None:
            s3 = self._s3()
            try:
                s3.head_bucket(Bucket=bucket)
                return  # already exists
            except ClientError as e:
                if e.response.get("Error", {}).get("Code") not in _ABSENT_BUCKET_CODES:
                    raise  # a real error (perms, connectivity) — surface it
            try:
                s3.create_bucket(Bucket=bucket)  # MinIO ignores region/location
            except ClientError as e:
                if e.response.get("Error", {}).get("Code") not in _ALREADY_OWNED_CODES:
                    raise  # not the benign create race — surface it
        await asyncio.to_thread(_ensure)

    async def healthcheck(self) -> dict:
        def _check() -> dict:
            try:
                self._s3().head_bucket(Bucket=self._bucket)
                return {"ok": True, "detail": f"bucket '{self._bucket}' reachable"}
            except Exception as e:  # noqa: BLE001
                return {"ok": False, "detail": f"{type(e).__name__}: {e}"}
        return await asyncio.to_thread(_check)
