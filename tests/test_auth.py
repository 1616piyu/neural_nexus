import pytest

from app import create_app
from config import Config
import database


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Create an isolated Flask app and database for each test."""
    monkeypatch.setattr(
        Config,
        "DATABASE_PATH",
        tmp_path / "test_neural_nexus.db",
    )

    app = create_app()
    app.config.update(
        TESTING=True,
        SECRET_KEY="test-secret-key-for-automated-tests",
    )

    with app.test_client() as test_client:
        yield test_client


def register(client, username="test_user",
             email="test@example.com",
             password="SecurePass123!"):
    return client.post(
        "/api/auth/register",
        json={
            "username": username,
            "email": email,
            "password": password,
        },
    )


def login(client, identifier="test_user",
          password="SecurePass123!"):
    return client.post(
        "/api/auth/login",
        json={
            "identifier": identifier,
            "password": password,
        },
    )


def test_register_success(client):
    response = register(client)

    assert response.status_code == 201
    assert response.json["user"]["username"] == "test_user"
    assert "password" not in response.json["user"]


def test_duplicate_username_rejected(client):
    register(client)

    response = register(
        client,
        email="another@example.com",
    )

    assert response.status_code == 400


def test_invalid_email_rejected(client):
    response = register(client, email="invalid-email")

    assert response.status_code == 400


def test_short_password_rejected(client):
    response = register(client, password="123")

    assert response.status_code == 400


def test_login_with_username(client):
    register(client)

    response = login(client)

    assert response.status_code == 200
    assert response.json["message"] == "Login successful."


def test_login_with_email(client):
    register(client)

    response = login(client, identifier="test@example.com")

    assert response.status_code == 200


def test_wrong_password_rejected(client):
    register(client)

    response = login(client, password="WrongPassword123!")

    assert response.status_code == 401


def test_current_user_requires_login(client):
    response = client.get("/api/auth/me")

    assert response.status_code == 401


def test_logout_clears_session(client):
    register(client)
    login(client)

    logout_response = client.post("/api/auth/logout")
    profile_response = client.get("/api/auth/me")

    assert logout_response.status_code == 200
    assert profile_response.status_code == 401


def test_database_stores_password_hash(client):
    register(client)

    user = database.get_user_by_username("test_user")

    assert user is not None
    assert user["password_hash"] != "SecurePass123!"
    assert user["password_hash"].startswith("scrypt:")