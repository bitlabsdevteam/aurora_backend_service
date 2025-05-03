"""
Flask application factory.

Creates and configures the Flask application.
"""
import os
from datetime import timedelta
from flask import Flask
from flask_jwt_extended import JWTManager

from aurora_backend_llm.db import init_app
from aurora_backend_llm.api.auth.routes import auth_bp
from aurora_backend_llm.api.user_routes import user_bp

def create_app(config=None):
    """
    Create and configure a Flask application.
    
    Args:
        config: Configuration object or dictionary
        
    Returns:
        Flask application instance
    """
    app = Flask(__name__)
    
    # Load default configuration
    app.config.from_mapping(
        SECRET_KEY=os.environ.get('SECRET_KEY', 'dev-key-change-in-production'),
        SQLALCHEMY_DATABASE_URI=os.environ.get(
            'DATABASE_URL', 
            'postgresql://postgres:postgres@localhost:5432/aurora'
        ),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        JWT_SECRET_KEY=os.environ.get('JWT_SECRET_KEY', 'jwt-secret-key-change-in-production'),
        JWT_ACCESS_TOKEN_EXPIRES=timedelta(hours=1),
        JWT_REFRESH_TOKEN_EXPIRES=timedelta(days=30),
    )
    
    # Override with provided configuration
    if config:
        app.config.from_mapping(config)
    
    # Initialize extensions
    db = init_app(app)
    jwt = JWTManager(app)
    
    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(user_bp)
    
    # JWT user loading
    @jwt.user_lookup_loader
    def user_lookup_callback(_jwt_header, jwt_data):
        """
        Callback to load user from JWT identity.
        """
        from aurora_backend_llm.db.models import User
        
        identity = jwt_data["sub"]
        return User.query.get(identity)
    
    # Shell context
    @app.shell_context_processor
    def make_shell_context():
        """
        Add database and models to the shell context.
        """
        from aurora_backend_llm.db import db, User
        
        return {
            'db': db,
            'User': User
        }
    
    return app 