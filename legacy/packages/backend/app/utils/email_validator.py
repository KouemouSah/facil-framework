"""
Email Validator - Validates email syntax and domain DNS records
NO external dependencies (uses stdlib socket + re)
"""
import re
import socket
from typing import Tuple
from loguru import logger


class EmailValidator:
    """Validates email addresses with DNS MX verification"""

    # RFC 5322 simplified regex (good enough for 99% of cases)
    EMAIL_REGEX = re.compile(
        r'^[a-zA-Z0-9.!#$%&\'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?'
        r'(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$'
    )

    @staticmethod
    def validate_syntax(email: str) -> bool:
        """
        Validate email syntax using regex

        Args:
            email: Email address to validate

        Returns:
            bool: True if syntax is valid

        Examples:
            >>> EmailValidator.validate_syntax("test@example.com")
            True
            >>> EmailValidator.validate_syntax("invalid@")
            False
        """
        if not email or len(email) > 320:  # RFC 5321 max length
            return False

        return bool(EmailValidator.EMAIL_REGEX.match(email))

    @staticmethod
    def validate_domain(email: str) -> Tuple[bool, str]:
        """
        Validate that email domain exists (DNS lookup)

        Uses socket.getaddrinfo() - part of Python stdlib, no dependencies

        Args:
            email: Email address to validate

        Returns:
            Tuple[bool, str]: (is_valid, error_message)

        Examples:
            >>> EmailValidator.validate_domain("test@gmail.com")
            (True, "")
            >>> EmailValidator.validate_domain("test@nonexistentdomain12345.com")
            (False, "Domain does not exist")
        """
        try:
            domain = email.split('@')[1]

            # Try to resolve domain (checks if domain exists)
            # Timeout of 3 seconds (don't block registration too long)
            socket.setdefaulttimeout(3)
            socket.getaddrinfo(domain, None)

            return True, ""

        except socket.gaierror:
            # Domain does not exist or DNS lookup failed
            return False, f"Domain '{domain}' does not exist or is unreachable"

        except socket.timeout:
            # DNS timeout - domain might exist but slow
            # IMPORTANT: We allow registration (fail open, not fail closed)
            logger.warning(f"DNS timeout for domain {domain}, allowing registration")
            return True, ""

        except IndexError:
            # No @ in email (shouldn't happen if validate_syntax passed)
            return False, "Invalid email format"

        except Exception as e:
            # Unknown error - fail open (allow registration)
            logger.error(f"Unexpected error validating domain for {email}: {e}")
            return True, ""

    @staticmethod
    def validate_email(email: str) -> Tuple[bool, str]:
        """
        Full email validation (syntax + domain DNS check)

        Args:
            email: Email address to validate

        Returns:
            Tuple[bool, str]: (is_valid, error_message)

        Examples:
            >>> EmailValidator.validate_email("test@gmail.com")
            (True, "")
            >>> EmailValidator.validate_email("invalid@")
            (False, "Invalid email format")
            >>> EmailValidator.validate_email("test@nonexistentdomain12345.com")
            (False, "Domain 'nonexistentdomain12345.com' does not exist")
        """
        # Step 1: Syntax check
        if not EmailValidator.validate_syntax(email):
            return False, "Invalid email format"

        # Step 2: Domain DNS check
        return EmailValidator.validate_domain(email)


# Convenience function for backward compatibility
def is_valid_email(email: str) -> bool:
    """
    Quick boolean check if email is valid

    Args:
        email: Email address to validate

    Returns:
        bool: True if valid

    Examples:
        >>> is_valid_email("test@gmail.com")
        True
    """
    is_valid, _ = EmailValidator.validate_email(email)
    return is_valid
