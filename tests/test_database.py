
import sqlite3

import pytest

import database
from config import Config


@pytest.fixture
def test_db(tmp_path, monkeypatch):
    """Give each test its own temporary database."""
    db_path = tmp_path / "test_neural_nexus.db"
    monkeypatch.setattr(Config, "DATABASE_PATH", db_path)

    database.initialize_database()
    yield db_path


def test_database_connection(test_db):
    assert database.check_database() is True


def test_create_and_find_user(test_db):
    user = database.create_user(
        "test_user",
        "test@example.com",
        "test-password-hash",
    )

    assert user["username"] == "test_user"
    assert user["email"] == "test@example.com"
    assert database.get_user_by_id(user["id"])["id"] == user["id"]
    assert database.get_user_by_username("TEST_USER")["id"] == user["id"]
    assert database.get_user_by_email("TEST@example.com")["id"] == user["id"]


def test_duplicate_user_is_rejected(test_db):
    database.create_user("test_user", "test@example.com", "hash")

    with pytest.raises(sqlite3.IntegrityError):
        database.create_user("test_user", "another@example.com", "hash")


def test_conversation_and_message_operations(test_db):
    user = database.create_user(
        "chat_user",
        "chat@example.com",
        "test-hash",
    )

    session = database.create_session(user["id"], "Test conversation")
    assert session is not None

    message = database.add_message(
        session["id"], user["id"], "user", "Hello Neural Nexus"
    )

    assert message["content"] == "Hello Neural Nexus"
    assert len(database.get_messages(session["id"], user["id"])) == 1
    assert len(database.list_sessions(user["id"])) == 1

    assert database.rename_session(
        session["id"], user["id"], "Renamed conversation"
    )

    assert database.get_session_for_user(
        session["id"], user["id"]
    )["title"] == "Renamed conversation"

    assert database.delete_session(session["id"], user["id"])
    assert database.get_messages(session["id"], user["id"]) is None


def test_users_cannot_access_another_users_session(test_db):
    first_user = database.create_user("user_one", "one@example.com", "hash")
    second_user = database.create_user("user_two", "two@example.com", "hash")

    session = database.create_session(first_user["id"])

    assert database.get_session_for_user(
        session["id"], second_user["id"]
    ) is None

    assert database.add_message(
        session["id"], second_user["id"], "user", "Unauthorized"
    ) is None
