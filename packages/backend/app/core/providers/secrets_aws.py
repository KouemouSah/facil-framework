"""AwsSecretsManagerProvider — AWS Secrets Manager (SecretsProvider, P2.1).

Cloud secrets provider implementing the same `SecretsProvider` ABC as env /
OpenBao. Region + an optional name prefix come from the DB config or the rendered
env; AWS credentials travel via env (AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY) or
an IAM role (boto3 default chain) — never through the config form. boto3 (sync)
is wrapped in asyncio.to_thread.
"""

from __future__ import annotations

import asyncio
import os

import boto3
from botocore.exceptions import ClientError

from app.core.providers.base import SecretsProvider, cfg


class AwsSecretsManagerProvider(SecretsProvider):
    code = "aws_secretsmanager"

    @classmethod
    def config_schema(cls):
        # AWS creds travel via env / IAM role — never declared here (SEC-001).
        return [
            cfg("region", "Region", required=True, hint="eu-west-1"),
            cfg("prefix", "Secret name prefix", hint="facil/ (optional)"),
        ]

    def __init__(self, config=None) -> None:
        super().__init__(config)
        self._region = self.config.get("region") or os.environ.get("AWS_REGION", "us-east-1")
        self._prefix = self.config.get("prefix") or ""
        self._access = self.config.get("access_key") or os.environ.get("AWS_ACCESS_KEY_ID", "")
        self._secret = self.config.get("secret_key") or os.environ.get("AWS_SECRET_ACCESS_KEY", "")
        self._client = None

    def _sm(self):
        if self._client is None:
            kwargs = {"region_name": self._region}
            if self._access and self._secret:
                kwargs["aws_access_key_id"] = self._access
                kwargs["aws_secret_access_key"] = self._secret
            self._client = boto3.client("secretsmanager", **kwargs)
        return self._client

    async def get_secret(self, name: str) -> str | None:
        def _get() -> str | None:
            try:
                r = self._sm().get_secret_value(SecretId=f"{self._prefix}{name}")
                return r.get("SecretString")
            except ClientError as e:
                # A missing secret is legitimately absent → None. Any other error
                # (access denied, throttling, network) must NOT be masked as absent.
                if e.response.get("Error", {}).get("Code") == "ResourceNotFoundException":
                    return None
                raise
        return await asyncio.to_thread(_get)

    async def healthcheck(self) -> dict:
        def _check() -> dict:
            try:
                self._sm().list_secrets(MaxResults=1)
                return {"ok": True, "detail": f"Secrets Manager reachable ({self._region})"}
            except Exception as e:  # noqa: BLE001
                return {"ok": False, "detail": f"{type(e).__name__}: {e}"}
        return await asyncio.to_thread(_check)
