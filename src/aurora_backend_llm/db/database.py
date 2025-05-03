"""
Database configuration and initialization.

Sets up the Flask-SQLAlchemy instance and provides database connection utilities.
"""
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

# Initialize SQLAlchemy with no settings
db = SQLAlchemy()
migrate = Migrate()

def init_app(app):
    """
    Initialize the SQLAlchemy database with the Flask app.
    
    Args:
        app: Flask application instance
    """
    db.init_app(app)
    migrate.init_app(app, db)
    
    # Import models here to ensure they're registered with SQLAlchemy
    from aurora_backend_llm.db.models import User  # noqa

    return db 