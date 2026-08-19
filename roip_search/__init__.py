"""ROIP chat search subsystem.

Imports are intentionally lazy so utility tests do not require PostgreSQL.
"""


def register_chat_search(app):
    from .db import initialize_database
    from .routes import chat_search_bp

    app.register_blueprint(chat_search_bp)
    initialize_database()

