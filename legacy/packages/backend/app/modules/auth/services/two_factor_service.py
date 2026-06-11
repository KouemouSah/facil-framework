"""
Two-Factor Authentication (2FA) Service for TaxasGE Backend.

TASK-M01-011: 2FA TOTP Implementation
Source: RAPPORT_MODULE_01_AUTHENTICATION.md lines 436-440

This service handles:
- TOTP secret generation
- QR code generation for authenticator apps
- TOTP code verification
- Backup codes generation and validation
- 2FA enable/disable operations
"""

import base64
import pyotp
import qrcode
import qrcode.image.svg
import secrets
import hashlib
import logging
from cryptography.fernet import Fernet
from io import BytesIO
from typing import List, Optional, Tuple
from datetime import datetime

from app.repositories.user_repository import UserRepository

logger = logging.getLogger(__name__)


def _get_fernet() -> Fernet:
    """Get Fernet instance for TOTP secret encryption."""
    from app.config import get_settings
    settings = get_settings()
    key = settings.TOTP_ENCRYPTION_KEY
    if not key:
        # Derive from JWT secret: SHA256 → base64-encode first 32 bytes → Fernet key
        jwt_secret = settings.JWT_SECRET_KEY
        derived = hashlib.sha256(jwt_secret.encode()).digest()
        key = base64.urlsafe_b64encode(derived)
    elif isinstance(key, str):
        key = key.encode()
    return Fernet(key)


class TwoFactorService:
    """
    Service for Two-Factor Authentication operations.

    Implements TOTP (Time-based One-Time Password) RFC 6238.
    """

    def __init__(self):
        self.user_repo = UserRepository()
        self.issuer_name = "TaxasGE"  # App name shown in authenticator

    def generate_secret(self) -> str:
        """
        Generate a random TOTP secret (base32 encoded).

        Returns:
            str: Base32-encoded secret (32 characters)

        Example:
            'JBSWY3DPEHPK3PXP'
        """
        return pyotp.random_base32()

    def generate_qr_code(self, user_email: str, secret: str) -> str:
        """
        Generate QR code for TOTP setup (SVG format).

        Args:
            user_email: User's email for identification in authenticator app
            secret: TOTP secret (base32 encoded)

        Returns:
            str: SVG QR code as string

        QR Code Format:
            otpauth://totp/TaxasGE:user@example.com?secret=SECRET&issuer=TaxasGE

        Usage:
            User scans QR code with Google Authenticator, Authy, etc.
        """
        # Create TOTP provisioning URI
        totp = pyotp.TOTP(secret)
        provisioning_uri = totp.provisioning_uri(
            name=user_email,
            issuer_name=self.issuer_name
        )

        # Generate QR code (SVG format for web display)
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(provisioning_uri)
        qr.make(fit=True)

        # Create SVG image
        factory = qrcode.image.svg.SvgPathImage
        img = qr.make_image(image_factory=factory)

        # Convert to string
        buffer = BytesIO()
        img.save(buffer)
        svg_string = buffer.getvalue().decode('utf-8')

        return svg_string

    def verify_code(self, secret: str, code: str) -> bool:
        """
        Verify TOTP code against secret.

        Args:
            secret: TOTP secret (base32 encoded)
            code: 6-digit TOTP code from authenticator app

        Returns:
            bool: True if code is valid, False otherwise

        Time Window:
            - Accepts codes from current, previous, and next 30-second windows
            - Prevents replay attacks (code valid only once)

        Business Rules:
            - Code must be exactly 6 digits
            - Time-based (changes every 30 seconds)
            - Window: ±1 interval (90 seconds total)
        """
        if not code or len(code) != 6 or not code.isdigit():
            logger.warning("Invalid 2FA code format")
            return False

        try:
            totp = pyotp.TOTP(secret)
            # valid_window=1 means accept current, previous, and next code
            is_valid = totp.verify(code, valid_window=1)

            if is_valid:
                logger.info("2FA code verified successfully")
            else:
                logger.warning("2FA code verification failed")

            return is_valid

        except Exception as e:
            logger.error(f"Error verifying 2FA code: {e}")
            return False

    async def verify_code_with_replay_protection(
        self, secret: str, code: str, user_id: str
    ) -> bool:
        """
        Verify TOTP code with replay protection via Redis.
        Prevents the same code from being used twice within the valid window.
        """
        if not self.verify_code(secret, code):
            return False

        # Check replay: has this exact code been used by this user recently?
        try:
            from app.core.cache import get_cache
            cache = get_cache()
            replay_key = f"totp_used:{user_id}:{code}"

            # If key exists, this code was already used → reject
            existing = await cache.get(replay_key)
            if existing:
                logger.warning(f"TOTP replay detected for user {user_id}")
                return False

            # Mark code as used for 90 seconds (valid_window=1 → 3 × 30s intervals)
            await cache.set(replay_key, "1", ttl=90)
            return True

        except Exception as e:
            # FAIL CLOSED: If Redis is down, deny the code to prevent replay attacks
            logger.error(f"TOTP replay check failed (Redis?): {e} — denying code for security")
            return False

    def generate_backup_codes(self, count: int = 10) -> List[str]:
        """
        Generate backup codes for 2FA recovery.

        Args:
            count: Number of backup codes to generate (default: 10)

        Returns:
            List[str]: List of backup codes (8 characters each)

        Format:
            - 8 characters: 4 digits + dash + 4 digits
            - Example: '1234-5678'

        Business Rules:
            - User can use backup code if loses authenticator app
            - Each backup code can be used only once
            - Stored as hashed values in database
        """
        backup_codes = []

        for _ in range(count):
            # Generate 8 random digits
            code = ''.join([str(secrets.randbelow(10)) for _ in range(8)])
            # Format: XXXX-XXXX
            formatted_code = f"{code[:4]}-{code[4:]}"
            backup_codes.append(formatted_code)

        return backup_codes

    def hash_backup_code(self, code: str) -> str:
        """
        Hash backup code for secure storage.

        Args:
            code: Plain backup code (e.g., '1234-5678')

        Returns:
            str: SHA256 hash of code

        Security:
            - Backup codes stored as hashes (like passwords)
            - Cannot be reversed to get original code
        """
        return hashlib.sha256(code.encode()).hexdigest()

    def verify_backup_code(
        self,
        code: str,
        hashed_codes: List[str]
    ) -> Tuple[bool, Optional[List[str]]]:
        """
        Verify backup code and remove it if valid (one-time use).

        Args:
            code: Plain backup code from user
            hashed_codes: List of hashed backup codes from database

        Returns:
            Tuple[bool, Optional[List[str]]]:
                - bool: True if code is valid
                - List[str]: Updated list of remaining codes (or None if invalid)

        Business Rules:
            - Each backup code can be used only once
            - After use, code is removed from list
            - If all codes used, user must disable/re-enable 2FA
        """
        code_hash = self.hash_backup_code(code)

        if code_hash in hashed_codes:
            # Remove used code
            remaining_codes = [c for c in hashed_codes if c != code_hash]
            logger.info(f"Backup code used successfully. Remaining: {len(remaining_codes)}")
            return True, remaining_codes
        else:
            logger.warning("Invalid backup code")
            return False, None

    async def enable_2fa(self, user_id: str) -> dict:
        """
        Enable 2FA for user (Step 1: Generate secret and QR code).

        Args:
            user_id: User ID

        Returns:
            dict: {
                'secret': TOTP secret (for verification step — also cached in Redis),
                'qr_code': SVG QR code,
                'backup_codes': List of plain backup codes (show once!)
            }

        Workflow:
            1. Generate TOTP secret
            2. Cache secret in Redis (15min TTL) as pending
            3. Generate QR code for user to scan
            4. Generate backup codes
            5. Return data to user (secret also cached server-side)
            6. User scans QR code with authenticator app
            7. User calls verify_and_enable_2fa() with code from app
            8. If code valid, encrypt secret + save to DB + mark 2FA enabled

        Security:
            - Secret cached server-side in Redis (15min TTL)
            - Secret NOT saved to DB until verification
            - Prevents enabling 2FA without confirming user has working setup
        """
        # Get user email for QR code
        user = await self.user_repo.get_by_id(user_id)

        # Generate TOTP secret
        secret = self.generate_secret()

        # Generate QR code
        qr_code = self.generate_qr_code(user.get("email"), secret)

        # Generate backup codes
        backup_codes_plain = self.generate_backup_codes()

        # Cache pending secret + backup codes in Redis (15min TTL)
        try:
            import json
            from app.core.cache import get_cache
            cache = get_cache()
            pending_data = {
                "secret": secret,
                "backup_codes": backup_codes_plain,
            }
            await cache.set(f"2fa_pending:{user_id}", json.dumps(pending_data), ttl=900)
            logger.info(f"2FA pending secret cached in Redis for user {user_id} (15min TTL)")
        except Exception as e:
            logger.warning(f"Failed to cache 2FA pending secret in Redis: {e}")

        logger.info(f"Generated 2FA setup for user {user_id}")

        return {
            'secret': secret,
            'qr_code': qr_code,
            'backup_codes': backup_codes_plain
        }

    async def verify_and_enable_2fa(
        self,
        user_id: str,
        secret: str,
        code: str,
        backup_codes: List[str]
    ) -> bool:
        """
        Verify TOTP code and enable 2FA (Step 2: Confirm setup).

        Args:
            user_id: User ID
            secret: TOTP secret from enable_2fa() (also cached in Redis)
            code: 6-digit code from authenticator app
            backup_codes: Backup codes from enable_2fa() (plain text)

        Returns:
            bool: True if verification successful and 2FA enabled

        Workflow:
            1. Try to get pending data from Redis (preferred) or use provided secret
            2. Verify code against secret
            3. If valid:
                - Encrypt secret with Fernet before DB storage
                - Save backup codes to DB (hashed)
                - Set two_factor_enabled = True
                - Delete Redis pending data
            4. If invalid: Return False (do not save anything)

        Security:
            - Only enables 2FA after confirming user has working setup
            - TOTP secret encrypted with Fernet before DB storage
            - Backup codes hashed before storage
            - Redis pending data deleted after use
        """
        # Try to get pending secret from Redis (server-side source of truth)
        actual_secret = secret
        actual_backup_codes = backup_codes
        try:
            import json
            from app.core.cache import get_cache
            cache = get_cache()
            pending_raw = await cache.get(f"2fa_pending:{user_id}")
            if pending_raw:
                pending_data = json.loads(pending_raw) if isinstance(pending_raw, str) else pending_raw
                actual_secret = pending_data.get("secret", secret)
                actual_backup_codes = pending_data.get("backup_codes", backup_codes)
                logger.info(f"Using Redis-cached pending secret for user {user_id}")
        except Exception as e:
            logger.warning(f"Failed to read Redis 2FA pending data, using client-provided: {e}")

        # Verify code
        if not self.verify_code(actual_secret, code):
            logger.warning(f"2FA setup verification failed for user {user_id}: Invalid TOTP code")
            return False

        logger.info(f"TOTP code verified successfully for user {user_id}, proceeding with database save...")

        # Encrypt TOTP secret with Fernet before DB storage
        try:
            fernet = _get_fernet()
            encrypted_secret = fernet.encrypt(actual_secret.encode()).decode()
        except Exception as e:
            logger.error(f"🚨 CRITICAL: Failed to encrypt TOTP secret for user {user_id}: {e}")
            # SECURITY: Never store TOTP secrets in plaintext — fail the 2FA enable
            raise Exception("Failed to secure 2FA secret. Please try again or contact support.")

        # Hash backup codes
        hashed_codes = [self.hash_backup_code(bc) for bc in actual_backup_codes]

        # Save to database (encrypted secret)
        db_success = await self.user_repo.enable_two_factor(
            user_id=user_id,
            secret=encrypted_secret,
            backup_codes=hashed_codes
        )

        if not db_success:
            logger.error(f"❌ CRITICAL: TOTP code was valid but database save FAILED for user {user_id}. "
                       f"2FA will NOT be enabled. Check database logs for details.")
            return False

        # Clean up Redis pending data
        try:
            await cache.delete(f"2fa_pending:{user_id}")
        except Exception:
            pass

        logger.info(f"✅ 2FA enabled successfully for user {user_id} - encrypted secret saved to DB")
        return True

    async def disable_2fa(self, user_id: str) -> bool:
        """
        Disable 2FA for user.

        Args:
            user_id: User ID

        Returns:
            bool: True if disabled successfully

        Security:
            - Requires current password confirmation (done in endpoint)
            - Clears secret and backup codes from DB
            - Sets two_factor_enabled = False
        """
        await self.user_repo.disable_two_factor(user_id)
        logger.info(f"2FA disabled for user {user_id}")
        return True

    async def verify_login_code(
        self,
        user_id: str,
        code: str,
        allow_backup_code: bool = True
    ) -> bool:
        """
        Verify 2FA code during login.

        Args:
            user_id: User ID
            code: 6-digit TOTP code OR 8-char backup code
            allow_backup_code: Allow backup codes (default: True)

        Returns:
            bool: True if code is valid

        Workflow:
            1. Get user's 2FA secret and backup codes from DB
            2. Try verifying as TOTP code first
            3. If TOTP fails and backup codes allowed:
                - Try verifying as backup code
                - If valid, remove backup code from DB (one-time use)
            4. Return True if either verification succeeded

        Business Rules:
            - TOTP codes change every 30 seconds
            - Backup codes can be used only once
            - After all backup codes used, user should re-enable 2FA
        """
        import json

        # Get user data from DB (returns Dict[str, Any])
        user_data = await self.user_repo.get_by_id(user_id)

        if not user_data:
            logger.error(f"User {user_id} not found")
            return False

        # Access fields as dict (not object properties)
        two_factor_enabled = user_data.get("two_factor_enabled", False)
        two_factor_secret = user_data.get("two_factor_secret")

        if not two_factor_enabled or not two_factor_secret:
            logger.error(f"2FA not enabled for user {user_id} (enabled={two_factor_enabled}, has_secret={bool(two_factor_secret)})")
            return False

        # Decrypt TOTP secret (Fernet-encrypted in DB — migration 189)
        try:
            fernet = _get_fernet()
            secret_bytes = two_factor_secret.encode() if isinstance(two_factor_secret, str) else two_factor_secret
            decrypted_secret = fernet.decrypt(secret_bytes).decode()
        except Exception as e:
            logger.error(
                f"CRITICAL: Failed to decrypt TOTP secret for user {user_id}: {e}. "
                f"Possible cause: TOTP_ENCRYPTION_KEY or JWT_SECRET_KEY changed after 2FA setup. "
                f"Recovery: re-encrypt secrets with new key or user must disable/re-enable 2FA."
            )
            raise Exception("2FA verification temporarily unavailable. Please contact support or use a backup code.")

        # Try TOTP code first (with replay protection)
        logger.info(f"Verifying TOTP code for user {user_id}")
        if await self.verify_code_with_replay_protection(decrypted_secret, code, user_id):
            logger.info(f"✅ TOTP code verified successfully for user {user_id}")
            return True

        # Try backup code if allowed
        backup_codes_raw = user_data.get("two_factor_backup_codes")

        # Parse JSONB field if it's a string (asyncpg returns JSONB as JSON string)
        backup_codes = None
        if backup_codes_raw:
            if isinstance(backup_codes_raw, str):
                try:
                    backup_codes = json.loads(backup_codes_raw)
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse two_factor_backup_codes for user {user_id}")
            elif isinstance(backup_codes_raw, list):
                backup_codes = backup_codes_raw

        if allow_backup_code and backup_codes:
            logger.info(f"TOTP code failed, trying backup code for user {user_id}")
            is_valid, remaining_codes = self.verify_backup_code(code, backup_codes)

            if is_valid:
                logger.info(f"✅ Backup code verified successfully for user {user_id}")
                # Update backup codes in DB (remove used code)
                # CRITICAL: If update fails, do NOT grant access — the code would be reusable
                update_success = await self.user_repo.update_backup_codes(user_id, remaining_codes)
                if not update_success:
                    logger.error(
                        f"🚨 CRITICAL: Backup code verified but DB update FAILED for user {user_id}. "
                        "Denying access to prevent code reuse."
                    )
                    return False

                # Warn if running low on backup codes
                if len(remaining_codes) <= 2:
                    logger.warning(
                        f"User {user_id} has only {len(remaining_codes)} backup codes remaining"
                    )

                return True

        logger.warning(f"❌ 2FA login verification failed for user {user_id}: Neither TOTP code nor backup code was valid")
        return False


# Dependency injection
def get_two_factor_service() -> TwoFactorService:
    """Get TwoFactorService instance (for FastAPI Depends)."""
    return TwoFactorService()
