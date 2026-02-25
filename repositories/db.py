"""
Database connection pool for MySQL.

Framework-agnostic — uses mysql-connector-python's built-in pooling so
the same module works in Flask, FastAPI, Django, or plain scripts.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Generator

import mysql.connector
from mysql.connector import pooling


_pool: pooling.MySQLConnectionPool | None = None


def init_pool(
    host: str | None = None,
    port: int | None = None,
    user: str | None = None,
    password: str | None = None,
    database: str | None = None,
    pool_size: int = 5,
) -> pooling.MySQLConnectionPool:
    """Initialise (or re-initialise) the global connection pool.

    Parameters fall back to environment variables when not supplied:
        DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME
    """
    global _pool

    _pool = pooling.MySQLConnectionPool(
        pool_name='stripepoc_pool',
        pool_size=pool_size,
        pool_reset_session=True,
        host=host or os.getenv('DB_HOST', 'localhost'),
        port=port or int(os.getenv('DB_PORT', '3306')),
        user=user or os.getenv('DB_USER', 'root'),
        password=password or os.getenv('DB_PASSWORD', ''),
        database=database or os.getenv('DB_NAME', 'stripepoc'),
    )
    return _pool


def get_pool() -> pooling.MySQLConnectionPool:
    """Return the current pool, initialising it from env vars if needed."""
    global _pool
    if _pool is None:
        init_pool()
    return _pool


@contextmanager
def get_connection() -> Generator[mysql.connector.MySQLConnection, None, None]:
    """Yield a connection from the pool; returns it automatically on exit."""
    conn = get_pool().get_connection()
    try:
        yield conn
    finally:
        conn.close()  # returns to pool
