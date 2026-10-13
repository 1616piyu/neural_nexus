import re

from werkzeug.security import check_password_hash, generate_password_hash

import database


def normalize_email(email):
    """Normalize an email address."""
    if not isinstance(email, str):
        return ""

    return email.strip().lower()


def validate_registration(username, email, password):
    """Validate registration details and return an error if invalid."""
    if not all(isinstance(value, str) for value in (username, email, password)):
        return "All fields are required."

    username = username.strip()
    email = normalize_email(email)

    if not username or not email or not password:
        return "All fields are required."

    if len(username) < 3 or len(username) > 30:
        return "Username must be between 3 and 30 characters."

    if not re.fullmatch(r"[A-Za-z0-9_.-]+", username):
        return "Username can contain letters, numbers, dots, underscores and hyphens only."

    if len(email) > 254 or not re.fullmatch(
        r"[^@\s]+@[^@\s]+\.[^@\s]+", email
    ):
        return "Enter a valid email address."

    if len(password) < 8:
        return "Password must contain at least 8 characters."

    if len(password) > 128:
        return "Password must not exceed 128 characters."

    return None


def register_user(username, email, password):
    """Validate and create a user with a securely hashed password."""
    error = validate_registration(username, email, password)

    if error:
        return {"success": False, "error": error}

    username = username.strip()
    email = normalize_email(email)

    if database.get_user_by_username(username):
        return {"success": False, "error": "Username is already taken."}

    if database.get_user_by_email(email):
        return {"success": False, "error": "Email is already registered."}

    password_hash = generate_password_hash(password, method="scrypt")

    try:
        user = database.create_user(username, email, password_hash)
    except Exception as exc:
        # Handle a concurrent registration that creates a duplicate.
        import sqlite3

        if isinstance(exc, sqlite3.IntegrityError):
            return {
                "success": False,
                "error": "Username or email is already registered.",
            }
        raise

    return {
        "success": True,
        "user": {
            "id": user["id"],
            "username": user["username"],
            "email": user["email"],
        },
    }


def authenticate_user(identifier, password):
    """Authenticate by username or email."""
    if not isinstance(identifier, str) or not isinstance(password, str):
        return {"success": False, "error": "Invalid username/email or password."}

    identifier = identifier.strip()

    if not identifier or not password:
        return {"success": False, "error": "Invalid username/email or password."}

    if "@" in identifier:
        user = database.get_user_by_email(identifier)
    else:
        user = database.get_user_by_username(identifier)

    if not user or not check_password_hash(user["password_hash"], password):
        return {"success": False, "error": "Invalid username/email or password."}

    return {
        "success": True,
        "user": {
            "id": user["id"],
            "username": user["username"],
            "email": user["email"],
        },
    }