"""
Migration 189b: Encrypt plaintext TOTP secrets with Fernet.

Run once after deploying auth security hardening.
Usage: python 189_encrypt_totp_secrets.py

Requires: DATABASE_URL and JWT_SECRET_KEY env vars (or .env file).
"""
import asyncio
import os
import sys
import base64
import hashlib

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import asyncpg
from cryptography.fernet import Fernet, InvalidToken


def get_fernet(jwt_secret: str) -> Fernet:
    """Derive Fernet key from JWT secret (same as two_factor_service.py)."""
    derived = hashlib.sha256(jwt_secret.encode()).digest()
    key = base64.urlsafe_b64encode(derived)
    return Fernet(key)


def is_fernet_encrypted(value: str, fernet: Fernet) -> bool:
    """Check if a value is already Fernet-encrypted."""
    try:
        fernet.decrypt(value.encode())
        return True
    except (InvalidToken, Exception):
        return False


async def main():
    # Load env
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '.env'))

    database_url = os.getenv('DATABASE_URL')
    jwt_secret = os.getenv('JWT_SECRET_KEY')

    if not database_url or not jwt_secret:
        print("ERROR: DATABASE_URL and JWT_SECRET_KEY must be set")
        sys.exit(1)

    fernet = get_fernet(jwt_secret)
    conn = await asyncpg.connect(database_url)

    try:
        rows = await conn.fetch(
            "SELECT id, email, two_factor_secret FROM users WHERE two_factor_secret IS NOT NULL"
        )
        print(f"Found {len(rows)} users with TOTP secrets")

        encrypted_count = 0
        already_encrypted = 0

        for row in rows:
            secret = row['two_factor_secret']
            if is_fernet_encrypted(secret, fernet):
                already_encrypted += 1
                print(f"  {row['email']}: already encrypted")
                continue

            # Encrypt plaintext secret
            encrypted = fernet.encrypt(secret.encode()).decode()
            await conn.execute(
                "UPDATE users SET two_factor_secret = $1 WHERE id = $2",
                encrypted, row['id']
            )
            encrypted_count += 1
            print(f"  {row['email']}: encrypted successfully")

        print(f"\nDone: {encrypted_count} encrypted, {already_encrypted} already encrypted")

    finally:
        await conn.close()


if __name__ == '__main__':
    asyncio.run(main())
