"""
Safely enable DOCX uploads in the existing Neural Nexus SQLite database.

Run:
    python migrate_docx_support.py
"""

import sqlite3
import sys
from pathlib import Path

from config import Config


def migrate_documents_docx_support():
    database_path = Path(Config.DATABASE_PATH)
    database_path.parent.mkdir(parents=True, exist_ok=True)

    if not database_path.exists():
        raise FileNotFoundError(
            f"Database not found: {database_path}. "
            "Start the application once to initialize it."
        )

    connection = sqlite3.connect(str(database_path), timeout=30)

    try:
        connection.execute("PRAGMA foreign_keys = OFF")
        connection.execute("BEGIN IMMEDIATE")

        row = connection.execute(
            """
            SELECT sql
            FROM sqlite_master
            WHERE type = 'table' AND name = 'documents'
            """
        ).fetchone()

        if row is None:
            raise RuntimeError(
                "The documents table does not exist. Initialize the app first."
            )

        if "'docx'" in (row[0] or "").lower():
            connection.commit()
            print("DOCX support is already enabled.")
            return

        connection.execute(
            """
            CREATE TABLE documents_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                original_filename TEXT NOT NULL,
                stored_filename TEXT NOT NULL UNIQUE,
                file_type TEXT NOT NULL
                    CHECK (file_type IN ('pdf', 'txt', 'docx')),
                file_size INTEGER NOT NULL,
                extracted_text TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'processed'
                    CHECK (status IN ('processed', 'failed')),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id)
                    REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )

        connection.execute(
            """
            INSERT INTO documents_new (
                id, user_id, original_filename, stored_filename,
                file_type, file_size, extracted_text, status, created_at
            )
            SELECT
                id, user_id, original_filename, stored_filename,
                file_type, file_size, extracted_text, status, created_at
            FROM documents
            """
        )

        connection.execute("DROP TABLE documents")
        connection.execute(
            "ALTER TABLE documents_new RENAME TO documents"
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_documents_user
            ON documents(user_id)
            """
        )

        violations = connection.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()

        if violations:
            raise RuntimeError(
                f"Foreign-key validation failed: {violations[0]}"
            )

        connection.commit()
        print("Success! PDF, TXT, and DOCX are now allowed.")
        print(f"Database: {database_path}")

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


if __name__ == "__main__":
    try:
        migrate_documents_docx_support()
    except Exception as exc:
        print(f"Migration failed: {exc}")
        print("The migration was rolled back.")
        sys.exit(1)