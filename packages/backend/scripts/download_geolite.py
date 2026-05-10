#!/usr/bin/env python3
"""Download MaxMind GeoLite2-City.mmdb for offline GeoIP lookups (Phase C.4).

Why offline (rather than ip-api.com / Cloudflare header):
- ~10 µs in-memory lookup (vs ~50 ms HTTP round-trip)
- No rate limit (vs 45 req/min on ip-api.com free tier)
- RGPD-safe: client IPs never leave the backend

The MaxMind GeoLite2 database is updated weekly. This script must be run
periodically (cron monthly) to keep the database fresh. New AWS / GCP IP
ranges allocated after the last refresh will not be geolocated.

Usage:
  cd packages/backend
  MAXMIND_LICENSE_KEY=xxx python scripts/download_geolite.py
  # → writes to /tmp/GeoLite2-City.mmdb (or $GEOIP_DB_PATH)

Env vars:
  MAXMIND_LICENSE_KEY    (required) — License key from www.maxmind.com/account
  GEOIP_DB_PATH    (optional, default /tmp/GeoLite2-City.mmdb)

Exit codes:
  0  success — file written, sha256 verified
  1  network error / extraction failure
  2  missing license key
  3  signature / archive integrity failure
"""

import hashlib
import os
import shutil
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

EDITION = "GeoLite2-City"
BASE_URL = "https://download.maxmind.com/app/geoip_download"
DEFAULT_TARGET = "/tmp/GeoLite2-City.mmdb"


def _download(license_key: str, suffix: str, target: Path) -> None:
    url = (
        f"{BASE_URL}?edition_id={EDITION}&license_key={license_key}"
        f"&suffix={suffix}"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "facil-geolite-fetcher/1.0"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        if resp.status != 200:
            raise RuntimeError(f"HTTP {resp.status} from MaxMind")
        with open(target, "wb") as out:
            shutil.copyfileobj(resp, out)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    license_key = os.environ.get("MAXMIND_LICENSE_KEY")
    if not license_key:
        print("ERROR: MAXMIND_LICENSE_KEY env var is required", file=sys.stderr)
        print(
            "Sign up at https://www.maxmind.com/en/geolite2/signup "
            "and create a license key under Account → My License Key.",
            file=sys.stderr,
        )
        return 2

    target_path = Path(os.environ.get("GEOIP_DB_PATH", DEFAULT_TARGET))
    target_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="geolite_") as tmp:
        tmp = Path(tmp)
        archive = tmp / "geolite.tar.gz"
        sig = tmp / "geolite.tar.gz.sha256"

        # 1. Download archive + signature side-by-side
        try:
            _download(license_key, "tar.gz", archive)
            _download(license_key, "tar.gz.sha256", sig)
        except Exception as e:
            print(f"ERROR: download failed: {e}", file=sys.stderr)
            return 1

        # 2. Verify signature (MaxMind serves file as: "<sha256>  <filename>")
        with open(sig, "r", encoding="utf-8") as f:
            expected = f.read().split()[0].strip().lower()
        actual = _sha256(archive)
        if expected != actual:
            print(
                f"ERROR: sha256 mismatch — expected {expected}, got {actual}",
                file=sys.stderr,
            )
            return 3

        # 3. Extract the .mmdb file (only file we care about — drop everything else)
        with tarfile.open(archive, mode="r:gz") as tar:
            mmdb_member = next(
                (m for m in tar.getmembers() if m.name.endswith(".mmdb")), None
            )
            if mmdb_member is None:
                print("ERROR: archive contains no .mmdb file", file=sys.stderr)
                return 3
            f = tar.extractfile(mmdb_member)
            if f is None:
                print("ERROR: cannot extract mmdb member", file=sys.stderr)
                return 3
            with open(target_path, "wb") as out:
                shutil.copyfileobj(f, out)

    size_mb = target_path.stat().st_size / (1024 * 1024)
    print(f"SUCCESS: wrote {target_path} ({size_mb:.1f} MB, sha256 verified)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
