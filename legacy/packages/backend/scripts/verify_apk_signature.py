#!/usr/bin/env python3
"""
APK signature + ADI token verifier.

Reads an Android APK, parses the v2 APK Signing Block, extracts the first
X.509 certificate and prints its SHA-1 + SHA-256 fingerprints. Also checks
whether assets/adi-registration.properties is present (Play Console developer
verification token, see docs/documentation/mobile-publishing.html).

Pure Python, no Java / Android SDK required.

Usage:
    python scripts/verify-apk-signature.py path/to/app.apk [path/to/app2.apk ...]

Expected SHA-256 for the Facil citizen upload key:
    C4:78:D6:B0:6D:88:5F:E6:20:AA:DB:B7:2B:00:73:F4:57:C1:64:F8:47:9E:63:D5:AC:78:3B:3C:23:AD:87:1E
"""
from __future__ import annotations

import hashlib
import struct
import sys
import zipfile

EXPECTED_FACIL_CITIZEN = (
    "C4:78:D6:B0:6D:88:5F:E6:20:AA:DB:B7:2B:00:73:F4:"
    "57:C1:64:F8:47:9E:63:D5:AC:78:3B:3C:23:AD:87:1E"
)
EXPECTED_ADI_TOKEN_CITIZEN = "CXZYNVIZWNFLAAAAAAAAAAAAAA"


def _find_signing_block(data: bytes) -> bytes | None:
    eocd = data.rfind(b"PK\x05\x06")
    if eocd < 0:
        return None
    cd_off = struct.unpack("<I", data[eocd + 16 : eocd + 20])[0]
    if data[cd_off - 16 : cd_off] != b"APK Sig Block 42":
        return None
    sig_size = struct.unpack("<Q", data[cd_off - 24 : cd_off - 16])[0]
    return data[cd_off - 8 - sig_size : cd_off]


def _lp_u32(buf: bytes, off: int = 0) -> tuple[int, bytes, int]:
    n = struct.unpack("<I", buf[off : off + 4])[0]
    return n, buf[off + 4 : off + 4 + n], off + 4 + n


def _format_fingerprint(digest: bytes) -> str:
    return ":".join(f"{b:02X}" for b in digest)


def extract_first_cert(apk_path: str) -> dict[str, str]:
    """Return scheme -> SHA-256 / SHA-1 fingerprints of the first signer cert."""
    with open(apk_path, "rb") as f:
        data = f.read()
    block = _find_signing_block(data)
    if block is None:
        return {}
    out: dict[str, dict[str, str]] = {}
    pos, end = 8, len(block) - 24
    while pos < end:
        pair_size = struct.unpack("<Q", block[pos : pos + 8])[0]
        pair_id = struct.unpack("<I", block[pos + 8 : pos + 12])[0]
        value = block[pos + 12 : pos + 8 + pair_size]
        if pair_id in (0x7109871A, 0xF05368C0):  # v2 / v3
            _, signers, _ = _lp_u32(value, 0)
            _, signer, _ = _lp_u32(signers, 0)
            _, signed_data, _ = _lp_u32(signer, 0)
            digests_len, _, after_digests = _lp_u32(signed_data, 0)
            _, certs_array, _ = _lp_u32(signed_data, after_digests)
            _, cert_der, _ = _lp_u32(certs_array, 0)
            scheme = "v2" if pair_id == 0x7109871A else "v3"
            out[scheme] = {
                "sha1": _format_fingerprint(hashlib.sha1(cert_der).digest()),
                "sha256": _format_fingerprint(hashlib.sha256(cert_der).digest()),
                "cert_size": str(len(cert_der)),
            }
        pos += 8 + pair_size
    return out  # type: ignore[return-value]


def check_adi_token(apk_path: str) -> tuple[bool, str | None]:
    """Return (present, content) for assets/adi-registration.properties."""
    with zipfile.ZipFile(apk_path) as z:
        for name in z.namelist():
            if name == "assets/adi-registration.properties":
                return True, z.read(name).decode("utf-8").strip()
    return False, None


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    overall_ok = True
    for path in argv:
        print(f"=== {path} ===")
        try:
            schemes = extract_first_cert(path)
        except FileNotFoundError:
            print(f"  ERROR: file not found")
            overall_ok = False
            continue
        if not schemes:
            print("  ERROR: no APK Signing Block found (unsigned APK?)")
            overall_ok = False
            continue
        for scheme, fp in schemes.items():
            print(f"  {scheme}: cert {fp['cert_size']} bytes")
            print(f"     SHA-1   : {fp['sha1']}")
            print(f"     SHA-256 : {fp['sha256']}")
            if fp["sha256"] == EXPECTED_FACIL_CITIZEN:
                print("     -> matches Facil citizen registered key")
        present, content = check_adi_token(path)
        if not present:
            print("  ADI token : MISSING (Play Console will reject)")
            overall_ok = False
        else:
            mark = " (matches expected)" if content == EXPECTED_ADI_TOKEN_CITIZEN else ""
            print(f"  ADI token : {content}{mark}")
        print()
    print("RESULT:", "READY" if overall_ok else "NOT READY")
    return 0 if overall_ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
