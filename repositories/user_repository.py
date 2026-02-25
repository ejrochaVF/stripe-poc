"""
UserRepository — data-access layer for the `users` table.

All SQL lives here; the service layer never touches the database directly.
Uses parameterised queries to prevent SQL injection.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from repositories.db import get_connection


# Column list shared by all SELECT queries so we don't repeat ourselves.
_USER_COLUMNS = 'id, email, password_hash, created_at, updated_at'


@dataclass
class UserRow:
    """Represents a single row from the `users` table."""
    id: int
    email: str
    password_hash: str
    created_at: datetime
    updated_at: datetime


class UserRepository:
    """CRUD operations for the ``users`` table."""

    # ------------------------------------------------------------------ #
    # Reads                                                                #
    # ------------------------------------------------------------------ #

    def find_by_email(self, email: str) -> Optional[UserRow]:
        """Return a UserRow for the given email, or None if not found."""
        sql = f'SELECT {_USER_COLUMNS} FROM users WHERE email = %s LIMIT 1'
        with get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(sql, (email,))
            row = cursor.fetchone()
            cursor.close()
        if row is None:
            return None
        return UserRow(**row)

    def find_by_id(self, user_id: int) -> Optional[UserRow]:
        """Return a UserRow for the given ID, or None if not found."""
        sql = f'SELECT {_USER_COLUMNS} FROM users WHERE id = %s LIMIT 1'
        with get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(sql, (user_id,))
            row = cursor.fetchone()
            cursor.close()
        if row is None:
            return None
        return UserRow(**row)

    def exists(self, email: str) -> bool:
        """Return True if a user with this email already exists."""
        sql = 'SELECT 1 FROM users WHERE email = %s LIMIT 1'
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (email,))
            found = cursor.fetchone() is not None
            cursor.close()
        return found

    # ------------------------------------------------------------------ #
    # Writes                                                               #
    # ------------------------------------------------------------------ #

    def create(self, email: str, password_hash: str) -> int:
        """Insert a new user and return the generated ID.

        Raises ``mysql.connector.IntegrityError`` if the email is a duplicate.
        """
        sql = 'INSERT INTO users (email, password_hash) VALUES (%s, %s)'
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (email, password_hash))
            conn.commit()
            user_id = cursor.lastrowid
            cursor.close()
        return user_id

    def update_password(self, user_id: int, password_hash: str) -> bool:
        """Update the password hash for an existing user. Returns True if a row was changed."""
        sql = 'UPDATE users SET password_hash = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s'
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (password_hash, user_id))
            conn.commit()
            affected = cursor.rowcount
            cursor.close()
        return affected > 0

    def delete(self, user_id: int) -> bool:
        """Delete a user by ID. Returns True if a row was removed."""
        sql = 'DELETE FROM users WHERE id = %s'
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (user_id,))
            conn.commit()
            affected = cursor.rowcount
            cursor.close()
        return affected > 0
