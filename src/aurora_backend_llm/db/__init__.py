"""
Database module for the application.

Initializes the SQLAlchemy database and provides models and migration utilities.
"""
from aurora_backend_llm.db.database import db, migrate, init_app
from aurora_backend_llm.db.models import User

__all__ = ['db', 'migrate', 'init_app', 'User'] 