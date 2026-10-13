
import sqlite3
from contextlib import contextmanager

from config import Config


@contextmanager
def get_connection():
    """Open a SQLite connection and always close it."""
    Config.DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(
        str(Config.DATABASE_PATH),
        timeout=10,
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")

    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize_database():
    """Create all required tables and indexes."""
    schema = """
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL COLLATE NOCASE UNIQUE,
        email TEXT NOT NULL COLLATE NOCASE UNIQUE,
        password_hash TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS chat_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        title TEXT NOT NULL DEFAULT 'New conversation',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id)
            REFERENCES users(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id INTEGER NOT NULL,
        role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
        content TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (session_id)
            REFERENCES chat_sessions(id) ON DELETE CASCADE
    );

    CREATE INDEX IF NOT EXISTS idx_sessions_user
        ON chat_sessions(user_id);

    CREATE INDEX IF NOT EXISTS idx_messages_session
        ON messages(session_id);
    
    CREATE TABLE IF NOT EXISTS documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        original_filename TEXT NOT NULL,
        stored_filename TEXT NOT NULL UNIQUE,
        file_type TEXT NOT NULL CHECK (file_type IN ('pdf', 'txt', 'docx')),
        file_size INTEGER NOT NULL,
        extracted_text TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'processed'
            CHECK (status IN ('processed', 'failed')),
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id)
            REFERENCES users(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS document_chunks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        document_id INTEGER NOT NULL,
        chunk_index INTEGER NOT NULL,
        content TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (document_id)
            REFERENCES documents(id) ON DELETE CASCADE,
        UNIQUE (document_id, chunk_index)
    );

    CREATE INDEX IF NOT EXISTS idx_documents_user
        ON documents(user_id);

    CREATE INDEX IF NOT EXISTS idx_chunks_document
        ON document_chunks(document_id);

    CREATE TABLE IF NOT EXISTS chunk_embeddings (
        chunk_id INTEGER PRIMARY KEY,
        embedding BLOB NOT NULL,
        dimension INTEGER NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (chunk_id)
            REFERENCES document_chunks(id) ON DELETE CASCADE
    );
    """

    with get_connection() as connection:
        connection.executescript(schema)


def check_database():
    """Return True if the database can execute a query."""
    with get_connection() as connection:
        result = connection.execute("SELECT 1").fetchone()
        return result[0] == 1


# -------------------------
# User operations
# -------------------------

def create_user(username, email, password_hash):
    """Create a user. Password hashing is handled by the auth layer."""
    username = username.strip()
    email = email.strip().lower()

    if not username or not email or not password_hash:
        raise ValueError("Username, email and password hash are required.")

    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO users (username, email, password_hash)
            VALUES (?, ?, ?)
            """,
            (username, email, password_hash),
        )
        user_id = cursor.lastrowid

    return get_user_by_id(user_id)


def get_user_by_id(user_id):
    """Find a user by their ID."""
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT id, username, email, password_hash, created_at
            FROM users
            WHERE id = ?
            """,
            (user_id,),
        ).fetchone()

    return dict(row) if row else None


def get_user_by_username(username):
    """Find a user by username, case-insensitively."""
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT id, username, email, password_hash, created_at
            FROM users
            WHERE username = ? COLLATE NOCASE
            """,
            (username.strip(),),
        ).fetchone()

    return dict(row) if row else None


def get_user_by_email(email):
    """Find a user by email, case-insensitively."""
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT id, username, email, password_hash, created_at
            FROM users
            WHERE email = ? COLLATE NOCASE
            """,
            (email.strip(),),
        ).fetchone()

    return dict(row) if row else None


# -------------------------
# Conversation operations
# -------------------------

def create_session(user_id, title="New conversation"):
    """Create a conversation belonging to a user."""
    title = title.strip() or "New conversation"

    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO chat_sessions (user_id, title)
            VALUES (?, ?)
            """,
            (user_id, title),
        )
        session_id = cursor.lastrowid

    return get_session_for_user(session_id, user_id)


def get_session_for_user(session_id, user_id):
    """Return a conversation only if it belongs to the specified user."""
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT id, user_id, title, created_at, updated_at
            FROM chat_sessions
            WHERE id = ? AND user_id = ?
            """,
            (session_id, user_id),
        ).fetchone()

    return dict(row) if row else None


def list_sessions(user_id):
    """List a user's conversations, newest activity first."""
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, user_id, title, created_at, updated_at
            FROM chat_sessions
            WHERE user_id = ?
            ORDER BY updated_at DESC, id DESC
            """,
            (user_id,),
        ).fetchall()

    return [dict(row) for row in rows]


def rename_session(session_id, user_id, title):
    """Rename a conversation owned by the user."""
    title = title.strip()

    if not title:
        raise ValueError("Conversation title cannot be empty.")

    with get_connection() as connection:
        cursor = connection.execute(
            """
            UPDATE chat_sessions
            SET title = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND user_id = ?
            """,
            (title, session_id, user_id),
        )

    return cursor.rowcount == 1


def delete_session(session_id, user_id):
    """Delete a user's conversation and its messages."""
    with get_connection() as connection:
        cursor = connection.execute(
            """
            DELETE FROM chat_sessions
            WHERE id = ? AND user_id = ?
            """,
            (session_id, user_id),
        )

    return cursor.rowcount == 1


# -------------------------
# Message operations
# -------------------------

def add_message(session_id, user_id, role, content):
    """Save a message only when the conversation belongs to the user."""
    if role not in ("user", "assistant"):
        raise ValueError("Role must be 'user' or 'assistant'.")

    if not isinstance(content, str) or not content.strip():
        raise ValueError("Message content cannot be empty.")

    with get_connection() as connection:
        session = connection.execute(
            """
            SELECT id FROM chat_sessions
            WHERE id = ? AND user_id = ?
            """,
            (session_id, user_id),
        ).fetchone()

        if session is None:
            return None

        cursor = connection.execute(
            """
            INSERT INTO messages (session_id, role, content)
            VALUES (?, ?, ?)
            """,
            (session_id, role, content.strip()),
        )

        message_id = cursor.lastrowid

        connection.execute(
            """
            UPDATE chat_sessions
            SET updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND user_id = ?
            """,
            (session_id, user_id),
        )

        row = connection.execute(
            """
            SELECT id, session_id, role, content, created_at
            FROM messages WHERE id = ?
            """,
            (message_id,),
        ).fetchone()

    return dict(row)


def get_messages(session_id, user_id):
    """Retrieve messages only for a conversation owned by the user."""
    with get_connection() as connection:
        session = connection.execute(
            """
            SELECT id FROM chat_sessions
            WHERE id = ? AND user_id = ?
            """,
            (session_id, user_id),
        ).fetchone()

        if session is None:
            return None

        rows = connection.execute(
            """
            SELECT id, session_id, role, content, created_at
            FROM messages
            WHERE session_id = ?
            ORDER BY id ASC
            """,
            (session_id,),
        ).fetchall()

    return [dict(row) for row in rows]

def create_document(
    user_id,
    original_filename,
    stored_filename,
    file_type,
    file_size,
    extracted_text,
    chunks,
    embeddings=None,
):
    """Save a document, its chunks, and optional embeddings atomically."""

    if embeddings is not None and len(embeddings) != len(chunks):
        raise ValueError("Each document chunk must have one embedding.")

    with get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO documents (
                user_id,
                original_filename,
                stored_filename,
                file_type,
                file_size,
                extracted_text,
                status
            )
            VALUES (?, ?, ?, ?, ?, ?, 'processed')
            """,
            (
                user_id,
                original_filename,
                stored_filename,
                file_type,
                file_size,
                extracted_text,
            ),
        )

        document_id = cursor.lastrowid

        for index, chunk in enumerate(chunks):
            chunk_cursor = connection.execute(
                """
                INSERT INTO document_chunks (
                    document_id,
                    chunk_index,
                    content
                )
                VALUES (?, ?, ?)
                """,
                (document_id, index, chunk),
            )

            if embeddings is not None:
                embedding = embeddings[index]
                embedding_bytes = embedding.tobytes()
                dimension = int(embedding.shape[0])

                connection.execute(
                    """
                    INSERT INTO chunk_embeddings (
                        chunk_id,
                        embedding,
                        dimension
                    )
                    VALUES (?, ?, ?)
                    """,
                    (
                        chunk_cursor.lastrowid,
                        embedding_bytes,
                        dimension,
                    ),
                )

        row = connection.execute(
            """
            SELECT
                id,
                user_id,
                original_filename,
                file_type,
                file_size,
                status,
                created_at
            FROM documents
            WHERE id = ?
            """,
            (document_id,),
        ).fetchone()

    return dict(row)



def list_documents(user_id):
    """List only documents owned by the specified user."""
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, original_filename, file_type, file_size,
                   status, created_at
            FROM documents
            WHERE user_id = ?
            ORDER BY id DESC
            """,
            (user_id,),
        ).fetchall()

    return [dict(row) for row in rows]


def get_document_for_user(document_id, user_id):
    """Find a document only if it belongs to the specified user."""
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT id, user_id, original_filename, stored_filename,
                   file_type, file_size, status, created_at
            FROM documents
            WHERE id = ? AND user_id = ?
            """,
            (document_id, user_id),
        ).fetchone()

    return dict(row) if row else None


def get_document_chunks(document_id, user_id):
    """Retrieve chunks only for a document owned by the user."""
    with get_connection() as connection:
        owner = connection.execute(
            """
            SELECT id FROM documents
            WHERE id = ? AND user_id = ?
            """,
            (document_id, user_id),
        ).fetchone()

        if owner is None:
            return None

        rows = connection.execute(
            """
            SELECT chunk_index, content
            FROM document_chunks
            WHERE document_id = ?
            ORDER BY chunk_index
            """,
            (document_id,),
        ).fetchall()

    return [dict(row) for row in rows]


def delete_document(document_id, user_id):
    """Delete a document and its chunks only for its owner."""
    with get_connection() as connection:
        cursor = connection.execute(
            """
            DELETE FROM documents
            WHERE id = ? AND user_id = ?
            """,
            (document_id, user_id),
        )

    return cursor.rowcount == 1

def save_chunk_embedding(chunk_id, user_id, embedding_bytes, dimension):
    """Save an embedding only for a chunk owned by the user."""
    if not isinstance(embedding_bytes, bytes) or not embedding_bytes:
        raise ValueError("Embedding must be non-empty bytes.")

    if not isinstance(dimension, int) or dimension <= 0:
        raise ValueError("Embedding dimension must be positive.")

    with get_connection() as connection:
        owner = connection.execute(
            """
            SELECT dc.id
            FROM document_chunks AS dc
            JOIN documents AS d ON d.id = dc.document_id
            WHERE dc.id = ? AND d.user_id = ?
            """,
            (chunk_id, user_id),
        ).fetchone()

        if owner is None:
            return False

        connection.execute(
            """
            INSERT INTO chunk_embeddings (chunk_id, embedding, dimension)
            VALUES (?, ?, ?)
            ON CONFLICT(chunk_id) DO UPDATE SET
                embedding = excluded.embedding,
                dimension = excluded.dimension,
                created_at = CURRENT_TIMESTAMP
            """,
            (chunk_id, embedding_bytes, dimension),
        )

    return True


def get_chunk_embeddings(user_id, document_id=None):
    """Return embeddings and chunk text for documents owned by the user."""
    query = """
        SELECT
            dc.id AS chunk_id,
            dc.document_id,
            dc.chunk_index,
            dc.content,
            ce.embedding,
            ce.dimension
        FROM document_chunks AS dc
        JOIN documents AS d ON d.id = dc.document_id
        JOIN chunk_embeddings AS ce ON ce.chunk_id = dc.id
        WHERE d.user_id = ?
    """
    parameters = [user_id]

    if document_id is not None:
        query += " AND d.id = ?"
        parameters.append(document_id)

    query += " ORDER BY dc.document_id, dc.chunk_index"

    with get_connection() as connection:
        rows = connection.execute(query, parameters).fetchall()

    return [dict(row) for row in rows]
