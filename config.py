import os
import secrets
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent

# Load local environment variables from the project root.
load_dotenv(BASE_DIR / ".env")


class Config:
    """Central configuration for the Neural Nexus application."""

    SECRET_KEY = os.getenv("FLASK_SECRET_KEY") or secrets.token_hex(32)

    DEBUG = os.getenv("FLASK_DEBUG", "false").strip().lower() == "true"
    HOST = os.getenv("FLASK_HOST", "127.0.0.1")
    PORT = int(os.getenv("FLASK_PORT", "5000"))

    DATABASE_PATH = Path(
        os.getenv("DATABASE_PATH", "data/neural_nexus.db")
    )

    # Resolve relative database paths from the project root.
    if not DATABASE_PATH.is_absolute():
        DATABASE_PATH = BASE_DIR / DATABASE_PATH

    MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10 MB upload limit

    MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "").strip()
    MISTRAL_MODEL = os.getenv(
        "MISTRAL_MODEL", "mistral-small-latest"
    ).strip()
