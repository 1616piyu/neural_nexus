import uuid
from pathlib import Path

from flask import (
    Flask,
    current_app,
    jsonify,
    render_template,
    request,
    session,
)
from werkzeug.exceptions import BadRequest
from werkzeug.utils import secure_filename
from services.search_service import search_documents
from services.rag_service import generate_answer

import database
from config import Config
from database import initialize_database, check_database
from services.auth_service import register_user, authenticate_user
from services.document_service import (
    validate_document,
    extract_document_text,
    chunk_text,
)
from services.embedding_service import generate_embeddings


def create_app():
    """Create and configure the Neural Nexus Flask application."""
    app = Flask(__name__)
    app.config.from_object(Config)

    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=not app.config["DEBUG"],
        MAX_CONTENT_LENGTH=10 * 1024 * 1024,
    )

    # Create database tables if they do not exist.
    initialize_database()

    # -------------------------
    # Basic and health endpoints
    # -------------------------

    @app.get("/")
    def index():
        return render_template("index.html")
    @app.get("/health")
    def health():
        try:
            database_ok = check_database()
        except Exception:
            app.logger.exception("Database health check failed")
            database_ok = False

        return jsonify({
            "status": "ok" if database_ok else "error",
            "database": "connected" if database_ok else "unavailable",
        }), 200 if database_ok else 503

    @app.errorhandler(413)
    def file_too_large(_error):
        return jsonify({
            "error": "The request exceeds the 10 MB upload limit."
        }), 413

    # -------------------------
    # Authentication endpoints
    # -------------------------

    @app.post("/api/auth/register")
    def register():
        try:
            data = request.get_json()
        except BadRequest:
            return jsonify({
                "error": "Request body must contain valid JSON."
            }), 400

        if not isinstance(data, dict):
            return jsonify({
                "error": "Request body must be a JSON object."
            }), 400

        result = register_user(
            data.get("username"),
            data.get("email"),
            data.get("password"),
        )

        if not result["success"]:
            return jsonify({"error": result["error"]}), 400

        return jsonify({
            "message": "Account created successfully.",
            "user": result["user"],
        }), 201

    @app.post("/api/auth/login")
    def login():
        try:
            data = request.get_json()
        except BadRequest:
            return jsonify({
                "error": "Request body must contain valid JSON."
            }), 400

        if not isinstance(data, dict):
            return jsonify({
                "error": "Request body must be a JSON object."
            }), 400

        identifier = data.get("identifier")

        if identifier is None:
            identifier = data.get("username") or data.get("email")

        result = authenticate_user(
            identifier,
            data.get("password"),
        )

        if not result["success"]:
            return jsonify({"error": result["error"]}), 401

        session.clear()
        session["user_id"] = result["user"]["id"]

        return jsonify({
            "message": "Login successful.",
            "user": result["user"],
        }), 200

    @app.post("/api/auth/logout")
    def logout():
        session.clear()

        return jsonify({
            "message": "Logout successful."
        }), 200

    @app.get("/api/auth/me")
    def current_user():
        user_id = session.get("user_id")

        if user_id is None:
            return jsonify({
                "error": "Authentication required."
            }), 401

        user = database.get_user_by_id(user_id)

        if user is None:
            session.clear()

            return jsonify({
                "error": "Authentication required."
            }), 401

        return jsonify({
            "user": {
                "id": user["id"],
                "username": user["username"],
                "email": user["email"],
            }
        }), 200

    # -------------------------
    # Document upload endpoint
    # -------------------------

    @app.post("/api/documents/upload")
    def upload_document():
        user_id = session.get("user_id")

        if user_id is None:
            return jsonify({
                "error": "Authentication required."
            }), 401

        uploaded_file = request.files.get("file")

        if uploaded_file is None or not uploaded_file.filename:
            return jsonify({
                "error": "Select a PDF or TXT file."
            }), 400

        # Normalize the client-provided filename before validating it.
        original_filename = secure_filename(
            Path(uploaded_file.filename).name
        )

        if not original_filename:
            return jsonify({
                "error": "Invalid filename."
            }), 400

        try:
            validate_document(original_filename)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400

        extension = Path(original_filename).suffix.lower()

        # Generate a unique filename; never use the supplied name as a path.
        stored_filename = f"{uuid.uuid4().hex}{extension}"

        upload_dir = (
            Path(__file__).resolve().parent
            / "uploads"
            / str(user_id)
        ).resolve()

        upload_dir.mkdir(parents=True, exist_ok=True)
        destination = upload_dir / stored_filename

        try:
            uploaded_file.save(destination)

            file_size = destination.stat().st_size

            # Validate actual bytes written to disk.
            validate_document(original_filename, file_size)

            extracted_text = extract_document_text(destination)
            chunks = chunk_text(extracted_text)

            if not chunks:
                raise ValueError(
                    "No usable text was found in the document."
                )

            # Generate a normalized 384-dimensional embedding per chunk.
            # Do this before writing document records to the database.
            embeddings = generate_embeddings(chunks)

            # Save document, chunks, and embeddings together.
            document = database.create_document(
                user_id=user_id,
                original_filename=original_filename,
                stored_filename=stored_filename,
                file_type=extension.lstrip("."),
                file_size=file_size,
                extracted_text=extracted_text,
                chunks=chunks,
                embeddings=embeddings,
            )

            return jsonify({
                "message": (
                    "Document uploaded and processed successfully."
                ),
                "document": document,
                "chunk_count": len(chunks),
            }), 201

        except ValueError as exc:
            destination.unlink(missing_ok=True)

            return jsonify({"error": str(exc)}), 400

        except Exception:
            destination.unlink(missing_ok=True)
            current_app.logger.exception(
                "Document upload failed"
            )

            return jsonify({
                "error": "Unable to process the document."
            }), 500

    # -------------------------
    # List a user's documents
    # -------------------------

    @app.get("/api/documents")
    def list_user_documents():
        user_id = session.get("user_id")

        if user_id is None:
            return jsonify({
                "error": "Authentication required."
            }), 401

        documents = database.list_documents(user_id)

        return jsonify({
            "documents": documents
        }), 200

    # -------------------------
    # Retrieve document chunks
    # -------------------------

    @app.get("/api/documents/<int:document_id>/chunks")
    def get_user_document_chunks(document_id):
        user_id = session.get("user_id")

        if user_id is None:
            return jsonify({
                "error": "Authentication required."
            }), 401

        chunks = database.get_document_chunks(
            document_id,
            user_id,
        )

        if chunks is None:
            # Do not reveal whether another user's document exists.
            return jsonify({
                "error": "Document not found."
            }), 404

        return jsonify({
            "document_id": document_id,
            "chunks": chunks,
        }), 200

    # -------------------------
    # Semantic search endpoint
    # -------------------------

    @app.post("/api/search")
    def semantic_search():
        user_id = session.get("user_id")

        if user_id is None:
            return jsonify({
                "error": "Authentication required."
            }), 401

        try:
            data = request.get_json()
        except BadRequest:
            return jsonify({
                "error": "Request body must contain valid JSON."
            }), 400

        if not isinstance(data, dict):
            return jsonify({
                "error": "Request body must be a JSON object."
            }), 400

        query = data.get("query")

        if not isinstance(query, str) or not query.strip():
            return jsonify({
                "error": "A non-empty search query is required."
            }), 400

        top_k = data.get("top_k", 5)

        if (
            isinstance(top_k, bool)
            or not isinstance(top_k, int)
            or not 1 <= top_k <= 10
        ):
            return jsonify({
                "error": "top_k must be an integer between 1 and 10."
            }), 400

        document_id = data.get("document_id")

        if document_id is not None:
            if (
                isinstance(document_id, bool)
                or not isinstance(document_id, int)
                or document_id <= 0
            ):
                return jsonify({
                    "error": "document_id must be a positive integer."
                }), 400

        try:
            results = search_documents(
                user_id=user_id,
                query=query,
                top_k=top_k,
                document_id=document_id,
            )

            return jsonify({
                "query": query.strip(),
                "count": len(results),
                "results": results,
            }), 200

        except ValueError as exc:
            return jsonify({
                "error": str(exc)
            }), 400

        except Exception:
            current_app.logger.exception(
                "Semantic search failed"
            )

            return jsonify({
                "error": "Unable to perform semantic search."
            }), 500
        # -------------------------
    # RAG chat endpoint
    # -------------------------

    @app.post("/api/chat")
    def chat():
        user_id = session.get("user_id")

        if user_id is None:
            return jsonify({
                "error": "Authentication required."
            }), 401

        try:
            data = request.get_json()
        except BadRequest:
            return jsonify({
                "error": "Request body must contain valid JSON."
            }), 400

        if not isinstance(data, dict):
            return jsonify({
                "error": "Request body must be a JSON object."
            }), 400

        question = data.get("message", data.get("question"))

        if not isinstance(question, str) or not question.strip():
            return jsonify({
                "error": "A non-empty message is required."
            }), 400

        question = question.strip()

        if len(question) > 5000:
            return jsonify({
                "error": "Message must not exceed 5000 characters."
            }), 400

        session_id = data.get("session_id")
        document_id = data.get("document_id")
        top_k = data.get("top_k", 5)

        if session_id is not None:
            if (
                isinstance(session_id, bool)
                or not isinstance(session_id, int)
                or session_id <= 0
            ):
                return jsonify({
                    "error": "session_id must be a positive integer."
                }), 400

            chat_session = database.get_session_for_user(
                session_id,
                user_id,
            )

            if chat_session is None:
                return jsonify({
                    "error": "Chat session not found."
                }), 404

        else:
            chat_session = database.create_session(
                user_id,
                title=question[:50],
            )

            if isinstance(chat_session, dict):
                session_id = chat_session["id"]
            else:
                session_id = chat_session

        if document_id is not None:
            if (
                isinstance(document_id, bool)
                or not isinstance(document_id, int)
                or document_id <= 0
            ):
                return jsonify({
                    "error": "document_id must be a positive integer."
                }), 400

            document = database.get_document_for_user(
                document_id,
                user_id,
            )

            if document is None:
                return jsonify({
                    "error": "Document not found."
                }), 404

        if (
            isinstance(top_k, bool)
            or not isinstance(top_k, int)
            or not 1 <= top_k <= 10
        ):
            return jsonify({
                "error": "top_k must be an integer between 1 and 10."
            }), 400

        try:
            result = generate_answer(
                user_id=user_id,
                question=question,
                document_id=document_id,
                top_k=top_k,
            )

            # Store the conversation only after answer generation succeeds.
            database.add_message(
                session_id,
                user_id,
                "user",
                question,
            )

            database.add_message(
                session_id,
                user_id,
                "assistant",
                result["answer"],
            )

            return jsonify({
                "session_id": session_id,
                "question": question,
                "answer": result["answer"],
                "sources": result["sources"],
            }), 200

        except ValueError as exc:
            return jsonify({
                "error": str(exc)
            }), 400

        except RuntimeError as exc:
            current_app.logger.warning(
                "RAG answer generation failed: %s",
                exc,
            )

            return jsonify({
                "error": str(exc)
            }), 503

        except Exception:
            current_app.logger.exception(
                "Chat request failed"
            )

            return jsonify({
                "error": "Unable to process your chat message."
            }), 500


    # -------------------------
    # Conversation history endpoints
    # -------------------------

    @app.get("/api/chat/sessions")
    def list_chat_sessions():
        user_id = session.get("user_id")

        if user_id is None:
            return jsonify({
                "error": "Authentication required."
            }), 401

        try:
            sessions = database.list_sessions(user_id)

            return jsonify({
                "sessions": sessions,
                "count": len(sessions),
            }), 200

        except Exception:
            current_app.logger.exception(
                "Failed to list chat sessions"
            )

            return jsonify({
                "error": "Unable to retrieve chat sessions."
            }), 500

    @app.get("/api/chat/sessions/<int:session_id>/messages")
    def get_chat_session_messages(session_id):
        user_id = session.get("user_id")

        if user_id is None:
            return jsonify({
                "error": "Authentication required."
            }), 401

        try:
            messages = database.get_messages(
                session_id,
                user_id,
            )

            if messages is None:
                return jsonify({
                    "error": "Chat session not found."
                }), 404

            return jsonify({
                "session_id": session_id,
                "messages": messages,
                "count": len(messages),
            }), 200

        except Exception:
            current_app.logger.exception(
                "Failed to retrieve chat messages"
            )

            return jsonify({
                "error": "Unable to retrieve chat messages."
            }), 500

    return app


app = create_app()


if __name__ == "__main__":
    app.run(
        host=Config.HOST,
        port=Config.PORT,
        debug=Config.DEBUG,
    )