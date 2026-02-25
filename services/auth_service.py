"""
AuthService — authentication business logic.

Framework-agnostic.  Depends on a UserRepository for data access and
uses bcrypt for secure password hashing (adaptive cost factor).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import bcrypt

from repositories.user_repository import UserRepository, UserRow


class AuthError(str, Enum):
    """Machine-readable error codes returned by AuthService."""
    INVALID_CREDENTIALS = 'invalid_credentials'
    EMAIL_ALREADY_EXISTS = 'email_already_exists'
    WEAK_PASSWORD = 'weak_password'


@dataclass
class AuthResult:
    """Outcome of an authentication or registration attempt."""
    success: bool
    user: UserRow | None = None
    error: AuthError | None = None
    message: str | None = None


class AuthService:
    """Handles user registration and credential verification.

    Usage:
        repo = UserRepository()
        auth = AuthService(repo)
        result = auth.login('user@example.com', 'p4$$word')
    """

    MIN_PASSWORD_LENGTH = 8

    def __init__(self, user_repository: UserRepository) -> None:
        self._repo = user_repository

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def login(self, email: str, password: str) -> AuthResult:
        """Verify credentials and return an AuthResult.

        On success ``result.user`` contains the matched UserRow.
        """
        if not email or not password:
            return AuthResult(
                success=False,
                error=AuthError.INVALID_CREDENTIALS,
                message='Email and password are required.',
            )

        user = self._repo.find_by_email(email)
        if user is None:
            # Perform a dummy hash check so the response time is constant
            # regardless of whether the email exists (timing-attack mitigation).
            self._dummy_check()
            return AuthResult(
                success=False,
                error=AuthError.INVALID_CREDENTIALS,
                message='Invalid email or password.',
            )

        if not self._verify_password(password, user.password_hash):
            return AuthResult(
                success=False,
                error=AuthError.INVALID_CREDENTIALS,
                message='Invalid email or password.',
            )

        return AuthResult(success=True, user=user)

    def register(self, email: str, password: str) -> AuthResult:
        """Create a new user account.

        Returns an AuthResult with the newly created UserRow on success.
        """
        if not email or not password:
            return AuthResult(
                success=False,
                error=AuthError.INVALID_CREDENTIALS,
                message='Email and password are required.',
            )

        if len(password) < self.MIN_PASSWORD_LENGTH:
            return AuthResult(
                success=False,
                error=AuthError.WEAK_PASSWORD,
                message=f'Password must be at least {self.MIN_PASSWORD_LENGTH} characters.',
            )

        if self._repo.exists(email):
            return AuthResult(
                success=False,
                error=AuthError.EMAIL_ALREADY_EXISTS,
                message='An account with this email already exists.',
            )

        hashed = self._hash_password(password)
        user_id = self._repo.create(email, hashed)
        user = self._repo.find_by_id(user_id)

        return AuthResult(success=True, user=user)

    def change_password(self, user_id: int, current_password: str, new_password: str) -> AuthResult:
        """Change a user's password after verifying the current one."""
        user = self._repo.find_by_id(user_id)
        if user is None:
            return AuthResult(
                success=False,
                error=AuthError.INVALID_CREDENTIALS,
                message='User not found.',
            )

        if not self._verify_password(current_password, user.password_hash):
            return AuthResult(
                success=False,
                error=AuthError.INVALID_CREDENTIALS,
                message='Current password is incorrect.',
            )

        if len(new_password) < self.MIN_PASSWORD_LENGTH:
            return AuthResult(
                success=False,
                error=AuthError.WEAK_PASSWORD,
                message=f'Password must be at least {self.MIN_PASSWORD_LENGTH} characters.',
            )

        hashed = self._hash_password(new_password)
        self._repo.update_password(user_id, hashed)

        return AuthResult(success=True, user=user)

    # ------------------------------------------------------------------ #
    # Password helpers                                                     #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _hash_password(password: str) -> str:
        """Hash a plain-text password with bcrypt (adaptive cost = 12)."""
        salt = bcrypt.gensalt(rounds=12)
        return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

    @staticmethod
    def _verify_password(password: str, password_hash: str) -> bool:
        """Check a plain-text password against a stored bcrypt hash."""
        return bcrypt.checkpw(
            password.encode('utf-8'),
            password_hash.encode('utf-8'),
        )

    @staticmethod
    def _dummy_check() -> None:
        """Perform a throwaway bcrypt comparison to equalise timing."""
        _dummy_hash = b'$2b$12$000000000000000000000000000000000000000000000000000000'
        try:
            bcrypt.checkpw(b'dummy', _dummy_hash)
        except Exception:
            pass
