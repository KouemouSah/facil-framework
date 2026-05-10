"""
Password Service for TaxasGE Backend
Handles password hashing and verification using bcrypt
"""

import asyncio
import bcrypt
from functools import partial
from typing import Optional
from loguru import logger


class PasswordService:
    """Service for password hashing and verification"""

    def __init__(self, rounds: int = 12):
        """
        Initialize password service

        Args:
            rounds: Number of bcrypt rounds (default 12, range 4-31)
                   Higher = more secure but slower
                   12 rounds = ~300ms, 14 rounds = ~1.2s
        """
        if not 4 <= rounds <= 31:
            raise ValueError("Bcrypt rounds must be between 4 and 31")

        self.rounds = rounds
        logger.info(f"PasswordService initialized with {rounds} bcrypt rounds")

    def _hash_password_sync(self, password: str) -> str:
        """Synchronous bcrypt hash (CPU-intensive, ~300ms at 12 rounds)"""
        salt = bcrypt.gensalt(rounds=self.rounds)
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')

    async def hash_password(self, password: str) -> str:
        """
        Hash a password using bcrypt (non-blocking via thread executor)

        Args:
            password: Plain text password

        Returns:
            str: Hashed password (bcrypt format: $2b$rounds$salt+hash)

        Raises:
            ValueError: If password is empty or invalid
            Exception: If hashing fails
        """
        try:
            # Validate password
            if not password or not isinstance(password, str):
                raise ValueError("Password must be a non-empty string")

            if len(password) < 8:
                raise ValueError("Password must be at least 8 characters")

            if len(password) > 72:
                raise ValueError("Password must not exceed 72 characters (bcrypt limit)")

            # Run bcrypt in thread executor to avoid blocking the event loop
            loop = asyncio.get_running_loop()
            hashed = await loop.run_in_executor(None, self._hash_password_sync, password)
            return hashed

        except ValueError as e:
            logger.error(f"Password validation error: {str(e)}")
            raise

        except Exception as e:
            logger.error(f"Error hashing password: {str(e)}")
            raise Exception(f"Failed to hash password: {str(e)}")

    def _verify_password_sync(self, password: str, hashed_password: str) -> bool:
        """Synchronous bcrypt verify (CPU-intensive)"""
        return bcrypt.checkpw(
            password.encode('utf-8'),
            hashed_password.encode('utf-8')
        )

    async def verify_password(self, password: str, hashed_password: str) -> bool:
        """
        Verify a password against a hashed password (non-blocking via thread executor)

        Args:
            password: Plain text password to verify
            hashed_password: Hashed password to compare against

        Returns:
            bool: True if password matches, False otherwise
        """
        try:
            # Validate inputs
            if not password or not hashed_password:
                logger.warning("Empty password or hash provided for verification")
                return False

            if not isinstance(password, str) or not isinstance(hashed_password, str):
                logger.warning("Invalid types for password verification")
                return False

            # Truncate password to bcrypt limit
            if len(password) > 72:
                password = password[:72]

            # Run bcrypt in thread executor to avoid blocking the event loop
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                None,
                partial(self._verify_password_sync, password, hashed_password)
            )

            if result:
                logger.debug("Password verification successful")
            else:
                logger.debug("Password verification failed")

            return result

        except Exception as e:
            logger.error(f"Error verifying password: {str(e)}")
            return False

    def check_password_strength(self, password: str) -> dict:
        """
        Check password strength and return detailed feedback

        Args:
            password: Plain text password to check

        Returns:
            dict: Password strength analysis
                {
                    "valid": bool,
                    "score": int (0-100),
                    "issues": List[str],
                    "suggestions": List[str]
                }
        """
        issues = []
        suggestions = []
        score = 0

        # Length check
        if len(password) < 8:
            issues.append("Password is too short")
            suggestions.append("Use at least 8 characters")
        elif len(password) >= 8:
            score += 20

        if len(password) >= 12:
            score += 10

        if len(password) >= 16:
            score += 10

        # Character diversity checks
        has_lowercase = any(c.islower() for c in password)
        has_uppercase = any(c.isupper() for c in password)
        has_digit = any(c.isdigit() for c in password)
        has_special = any(not c.isalnum() for c in password)

        if has_lowercase:
            score += 15
        else:
            issues.append("No lowercase letters")
            suggestions.append("Add lowercase letters (a-z)")

        if has_uppercase:
            score += 15
        else:
            issues.append("No uppercase letters")
            suggestions.append("Add uppercase letters (A-Z)")

        if has_digit:
            score += 15
        else:
            issues.append("No numbers")
            suggestions.append("Add numbers (0-9)")

        if has_special:
            score += 15
        else:
            issues.append("No special characters")
            suggestions.append("Add special characters (!@#$%^&*)")

        # Common patterns check
        common_patterns = [
            "password", "123456", "qwerty", "admin", "letmein",
            "welcome", "monkey", "dragon", "master", "sunshine"
        ]

        password_lower = password.lower()
        if any(pattern in password_lower for pattern in common_patterns):
            issues.append("Contains common password pattern")
            suggestions.append("Avoid common words and patterns")
            score = max(0, score - 30)

        # Sequential characters check
        if any(password[i:i+3].isdigit() and
               int(password[i+1]) == int(password[i]) + 1 and
               int(password[i+2]) == int(password[i+1]) + 1
               for i in range(len(password) - 2)
               if password[i:i+3].isdigit()):
            issues.append("Contains sequential numbers")
            suggestions.append("Avoid sequential patterns (123, 456, etc.)")
            score = max(0, score - 10)

        # Overall score adjustment
        score = min(100, max(0, score))

        return {
            "valid": len(issues) == 0 and score >= 60,
            "score": score,
            "strength": (
                "weak" if score < 40 else
                "fair" if score < 60 else
                "good" if score < 80 else
                "strong"
            ),
            "issues": issues,
            "suggestions": suggestions,
        }

    def needs_rehash(self, hashed_password: str) -> bool:
        """
        Check if a hashed password needs to be rehashed
        (e.g., if bcrypt rounds have been increased)

        Args:
            hashed_password: Hashed password to check

        Returns:
            bool: True if password should be rehashed
        """
        try:
            # Extract rounds from bcrypt hash
            # Format: $2b$12$... where 12 is the rounds
            if not hashed_password.startswith('$2b$'):
                logger.warning("Invalid bcrypt hash format")
                return True

            parts = hashed_password.split('$')
            if len(parts) < 4:
                return True

            current_rounds = int(parts[2])
            needs_rehash = current_rounds < self.rounds

            if needs_rehash:
                logger.info(f"Password needs rehash: {current_rounds} -> {self.rounds} rounds")

            return needs_rehash

        except Exception as e:
            logger.error(f"Error checking if password needs rehash: {str(e)}")
            return True


# Singleton instance with default configuration
_password_service_instance: Optional[PasswordService] = None


def get_password_service(rounds: int = 12) -> PasswordService:
    """
    Get password service singleton instance

    Args:
        rounds: Number of bcrypt rounds (only used on first call)

    Returns:
        PasswordService: Password service instance
    """
    global _password_service_instance

    if _password_service_instance is None:
        _password_service_instance = PasswordService(rounds=rounds)

    return _password_service_instance
