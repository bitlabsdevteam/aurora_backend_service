"""
Database models for the application.

Contains SQLAlchemy models that map to database tables.
"""
import datetime
from passlib.hash import bcrypt
from sqlalchemy.ext.hybrid import hybrid_property

from aurora_backend_llm.db.database import db

class User(db.Model):
    """
    User model for authentication and authorization.
    
    Stores user credentials and profile information.
    """
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    _password = db.Column('password', db.String(128), nullable=False)
    first_name = db.Column(db.String(50), nullable=True)
    last_name = db.Column(db.String(50), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    # For JWT token blacklisting/management
    last_login_at = db.Column(db.DateTime, nullable=True)
    token_version = db.Column(db.Integer, default=0)  # Increment to invalidate all previous tokens
    
    @hybrid_property
    def password(self):
        """
        Password property getter. We never expose the actual password.
        """
        raise AttributeError('Password is not a readable attribute')
    
    @password.setter
    def password(self, password):
        """
        Password setter - automatically hashes the password.
        """
        self._password = bcrypt.hash(password)
    
    def verify_password(self, password):
        """
        Verify a password against the stored hash.
        
        Args:
            password: The password to verify
            
        Returns:
            bool: True if password matches, False otherwise
        """
        return bcrypt.verify(password, self._password)
    
    @classmethod
    def get_by_username(cls, username):
        """
        Get a user by username.
        
        Args:
            username: Username to search for
            
        Returns:
            User: User object if found, None otherwise
        """
        return cls.query.filter_by(username=username).first()
    
    @classmethod
    def get_by_email(cls, email):
        """
        Get a user by email.
        
        Args:
            email: Email to search for
            
        Returns:
            User: User object if found, None otherwise
        """
        return cls.query.filter_by(email=email).first()
    
    def serialize(self):
        """
        Serialize user object to dictionary (for API responses).
        
        Returns:
            dict: Serialized user
        """
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'is_active': self.is_active,
            'is_admin': self.is_admin,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'last_login_at': self.last_login_at.isoformat() if self.last_login_at else None
        }
    
    def __repr__(self):
        return f'<User {self.username}>' 