"""S3StorageProvider — AWS S3 (and S3-compatible) object storage.

Cloud storage provider (P2.1). Region/bucket come from the DB config or the
rendered env (S3_REGION/S3_BUCKET). Credentials, when explicit, come from the env
the deploy layer renders (AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY) or a
vault-resolved config; otherwise boto3's default chain resolves an IAM role /
instance profile, so no long-lived keys are needed on AWS compute. An optional
`endpoint` targets S3-compatible stores (DigitalOcean Spaces, Wasabi, Cloudflare
R2). boto3 (sync) is wrapped in asyncio.to_thread so the async API is non-blocking.
"""

from __future__ import annotations

import asyncio
import os

import boto3
from botocore.exceptions import ClientError

from app.core.providers.base import StorageProvider, cfg

_ABSENT_BUCKET_CODES = {"404", "NoSuchBucket", "NotFound"}
# Course multi-replica : create_bucket perdant la course -> deja possede = succes idempotent.
_ALREADY_OWNED_CODES = {"BucketAlreadyOwnedByYou", "BucketAlreadyExists"}


class S3StorageProvider(StorageProvider):
    code = "s3"

    @classmethod
    def config_schema(cls):
        # Credentials (access_key/secret_key) travel via secret_ref / env / IAM
        # role — never declared here (SEC-001 / SEC-F2).
        return [
            cfg("region", "Region", required=True, hint="eu-west-1"),
            cfg("bucket", "Bucket", required=True, hint="my-app-documents"),
            cfg("endpoint", "Endpoint (S3-compatible)", hint="blank for AWS S3"),
        ]

    def __init__(self, config=None) -> None:
        super().__init__(config)
        self._region = (self.config.get("region")
                        or os.environ.get("S3_REGION") or os.environ.get("AWS_REGION", "us-east-1"))
        self._bucket = self.config.get("bucket") or os.environ.get("S3_BUCKET", "")
        self._endpoint = self.config.get("endpoint") or os.environ.get("S3_ENDPOINT") or None
        # Explicit creds are optional: absent → boto3 default chain (IAM role).
        self._access = self.config.get("access_key") or os.environ.get("AWS_ACCESS_KEY_ID", "")
        self._secret = self.config.get("secret_key") or os.environ.get("AWS_SECRET_ACCESS_KEY", "")
        self._client = None

    def _s3(self):
        if self._client is None:
            if not self._bucket:
                raise RuntimeError("S3 bucket is not configured (config.bucket / S3_BUCKET empty).")
            kwargs = {"region_name": self._region}
            if self._endpoint:
                kwargs["endpoint_url"] = self._endpoint
            # Explicit keys when provided (secret_ref / env); otherwise boto3's
            # default chain resolves an IAM role / instance profile (no static keys).
            if self._access and self._secret:
                kwargs["aws_access_key_id"] = self._access
                kwargs["aws_secret_access_key"] = self._secret
            self._client = boto3.client("s3", **kwargs)
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
                    raise  # a real error (AccessDenied, connectivity) — surface it
            kw: dict = {"Bucket": bucket}
            # AWS requires a LocationConstraint for every region except us-east-1.
            if self._region and self._region != "us-east-1":
                kw["CreateBucketConfiguration"] = {"LocationConstraint": self._region}
            try:
                s3.create_bucket(**kw)
            except ClientError as e:
                if e.response.get("Error", {}).get("Code") not in _ALREADY_OWNED_CODES:
                    raise  # not the benign create race — surface it
        await asyncio.to_thread(_ensure)

    async def healthcheck(self) -> dict:
        def _check() -> dict:
            try:
                self._s3().head_bucket(Bucket=self._bucket)
                return {"ok": True, "detail": f"bucket '{self._bucket}' reachable ({self._region})"}
            except Exception as e:  # noqa: BLE001
                return {"ok": False, "detail": f"{type(e).__name__}: {e}"}
        return await asyncio.to_thread(_check)
