"""
users.py — User account management for test_shop.

Provides user lookup, authentication, and profile management.
Other modules (checkout, payment, invoice) call get_user() and
authenticate_user() to verify identity before processing transactions.
"""

from typing import Optional


# Simulated in-memory user store
_USERS: dict[int, dict] = {
    1: {"id": 1, "name": "Alice", "email": "alice@example.com", "role": "customer"},
    2: {"id": 2, "name": "Bob",   "email": "bob@example.com",   "role": "customer"},
    3: {"id": 3, "name": "Admin", "email": "admin@example.com", "role": "admin"},
}


def get_user(user_id: int) -> Optional[dict]:
    """Return a user record by ID, or None if not found."""
    return _USERS.get(user_id)


def authenticate_user(user_id: int, token: str) -> bool:
    """
    Validate a session token for the given user.

    For the MVP this performs a simple token check.
    Returns True if the token is valid, False otherwise.
    """
    user = get_user(user_id)
    if user is None:
        return False
    # Simplified: any non-empty token is valid for existing users
    return bool(token)


def update_user_email(user_id: int, new_email: str) -> bool:
    """Update the email address of an existing user. Returns True on success."""
    user = get_user(user_id)
    if user is None:
        return False
    _USERS[user_id]["email"] = new_email
    return True


def list_users() -> list[dict]:
    """Return all users (admin-only operation in production)."""
    return list(_USERS.values())


def get_user_role(user_id: int) -> Optional[str]:
    """Return the role string for a user, or None if user does not exist."""
    user = get_user(user_id)
    if user is None:
        return None
    return user["role"]
