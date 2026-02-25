"""
Seed script — creates a test user in the database.

Usage:
    python seed_user.py

Reads DB connection details from .env (DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME).
"""

import os
import sys

from dotenv import load_dotenv

load_dotenv()

# Ensure project root is on the path so `repositories` / `services` resolve.
sys.path.insert(0, os.path.dirname(__file__))

from repositories.db import init_pool
from services.auth_service import AuthService
from repositories.user_repository import UserRepository


def main():
    init_pool()

    auth = AuthService(UserRepository())

    email = input('Email: ').strip()
    password = input('Password: ').strip()

    if not email or not password:
        print('Email and password are required.')
        sys.exit(1)

    result = auth.register(email, password)

    if result.success:
        print(f'User created — id={result.user.id}, email={result.user.email}')
    else:
        print(f'Failed: {result.message}')
        sys.exit(1)


if __name__ == '__main__':
    main()
