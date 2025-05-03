"""
Authentication routes for the API.

Provides endpoints for user registration, login, and token refresh.
"""
import datetime
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import (
    create_access_token, 
    create_refresh_token,
    jwt_required, 
    get_jwt_identity,
    current_user
)

from aurora_backend_llm.db.database import db
from aurora_backend_llm.db.models import User

# Create a Blueprint for auth routes
auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

@auth_bp.route('/register', methods=['POST'])
def register():
    """
    Register a new user.
    
    Request Body:
        username: Username for the new user
        email: Email for the new user
        password: Password for the new user
        first_name: (Optional) First name of the user
        last_name: (Optional) Last name of the user
        
    Returns:
        User info and access token
    """
    data = request.get_json()
    
    # Validate required fields
    required_fields = ['username', 'email', 'password']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'Missing required field: {field}'}), 400
    
    # Check if user already exists
    if User.get_by_username(data['username']):
        return jsonify({'error': 'Username already exists'}), 409
    
    if User.get_by_email(data['email']):
        return jsonify({'error': 'Email already exists'}), 409
    
    # Create new user
    user = User(
        username=data['username'],
        email=data['email'],
        first_name=data.get('first_name'),
        last_name=data.get('last_name')
    )
    user.password = data['password']  # This will hash the password
    
    # Save user to database
    db.session.add(user)
    db.session.commit()
    
    # Create tokens
    access_token = create_access_token(identity=user.id)
    refresh_token = create_refresh_token(identity=user.id)
    
    # Update last login time
    user.last_login_at = datetime.datetime.utcnow()
    db.session.commit()
    
    return jsonify({
        'user': user.serialize(),
        'access_token': access_token,
        'refresh_token': refresh_token
    }), 201

@auth_bp.route('/login', methods=['POST'])
def login():
    """
    Login a user.
    
    Request Body:
        username: Username or email of the user
        password: Password of the user
        
    Returns:
        User info and access token
    """
    data = request.get_json()
    
    # Validate required fields
    if not data.get('username') or not data.get('password'):
        return jsonify({'error': 'Username and password are required'}), 400
    
    # Check if user exists (support both username and email login)
    user = User.get_by_username(data['username'])
    if not user:
        user = User.get_by_email(data['username'])  # Try with email
    
    if not user or not user.verify_password(data['password']):
        return jsonify({'error': 'Invalid credentials'}), 401
    
    if not user.is_active:
        return jsonify({'error': 'Account is inactive'}), 403
    
    # Create tokens
    access_token = create_access_token(identity=user.id)
    refresh_token = create_refresh_token(identity=user.id)
    
    # Update last login time
    user.last_login_at = datetime.datetime.utcnow()
    db.session.commit()
    
    return jsonify({
        'user': user.serialize(),
        'access_token': access_token,
        'refresh_token': refresh_token
    }), 200

@auth_bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    """
    Refresh a user's access token.
    
    Requires a valid refresh token in the Authentication header.
    
    Returns:
        New access token
    """
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    
    if not user or not user.is_active:
        return jsonify({'error': 'User not found or inactive'}), 401
    
    # Create new access token
    access_token = create_access_token(identity=user_id)
    
    return jsonify({
        'access_token': access_token
    }), 200

@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def me():
    """
    Get current user information.
    
    Requires a valid access token in the Authentication header.
    
    Returns:
        Current user's information
    """
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    
    if not user or not user.is_active:
        return jsonify({'error': 'User not found or inactive'}), 401
    
    return jsonify({
        'user': user.serialize()
    }), 200 