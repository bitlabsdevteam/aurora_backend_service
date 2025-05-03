"""
API package for the Aurora Backend LLM service.

Contains routes and API service configuration.
"""
from aurora_backend_llm.api.auth.routes import auth_bp
from aurora_backend_llm.api.user_routes import user_bp

__all__ = ['auth_bp', 'user_bp']

__version__ = "1.0.0" 