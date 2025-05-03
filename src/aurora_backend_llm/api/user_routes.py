"""
User management API endpoints.

Provides CRUD operations for users.
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, current_user, get_jwt_identity
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime

from aurora_backend_llm.db.database import db
from aurora_backend_llm.db.models import User

# Create a Blueprint for user routes
user_bp = Blueprint('user', __name__, url_prefix='/api/users')

# Define Pydantic models for request validation
class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=80)
    email: EmailStr
    password: str = Field(..., min_length=8)
    first_name: Optional[str] = Field(None, max_length=50)
    last_name: Optional[str] = Field(None, max_length=50)
    is_active: bool = True
    is_admin: bool = False

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    password: Optional[str] = Field(None, min_length=8)
    first_name: Optional[str] = Field(None, max_length=50)
    last_name: Optional[str] = Field(None, max_length=50)
    is_active: Optional[bool] = None
    is_admin: Optional[bool] = None

# List all users
@user_bp.route('/', methods=['GET'])
@jwt_required()
def get_users():
    """
    Get all users.
    
    Requires admin privileges.
    
    Returns:
        List of users
    """
    # Check admin permissions
    user_id = get_jwt_identity()
    current_user = User.query.get(user_id)
    
    if not current_user or not current_user.is_admin:
        return jsonify({'error': 'Admin privileges required'}), 403
    
    # Pagination parameters
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    # Get users with pagination
    users = User.query.paginate(page=page, per_page=per_page)
    
    return jsonify({
        'users': [user.serialize() for user in users.items],
        'total': users.total,
        'page': users.page,
        'pages': users.pages,
        'per_page': users.per_page
    }), 200

# Get a specific user
@user_bp.route('/<int:user_id>', methods=['GET'])
@jwt_required()
def get_user(user_id):
    """
    Get a specific user by ID.
    
    Users can only access their own data unless they are admins.
    
    Args:
        user_id: ID of the user to retrieve
        
    Returns:
        User information
    """
    # Check permissions
    current_user_id = get_jwt_identity()
    current_user_obj = User.query.get(current_user_id)
    
    if not current_user_obj:
        return jsonify({'error': 'User not found'}), 404
    
    # Users can only access their own data unless they are admins
    if current_user_id != user_id and not current_user_obj.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403
    
    # Get requested user
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    return jsonify({
        'user': user.serialize()
    }), 200

# Create a new user
@user_bp.route('/', methods=['POST'])
@jwt_required()
def create_user():
    """
    Create a new user.
    
    Requires admin privileges.
    
    Request Body:
        username: Username for the new user
        email: Email for the new user
        password: Password for the new user
        first_name: (Optional) First name of the user
        last_name: (Optional) Last name of the user
        is_active: (Optional) Whether the user is active
        is_admin: (Optional) Whether the user is an admin
        
    Returns:
        Created user information
    """
    # Check admin permissions
    current_user_id = get_jwt_identity()
    current_user_obj = User.query.get(current_user_id)
    
    if not current_user_obj or not current_user_obj.is_admin:
        return jsonify({'error': 'Admin privileges required'}), 403
    
    data = request.get_json()
    
    # Validate data
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
        last_name=data.get('last_name'),
        is_active=data.get('is_active', True),
        is_admin=data.get('is_admin', False)
    )
    user.password = data['password']  # This will hash the password
    
    # Save user to database
    db.session.add(user)
    db.session.commit()
    
    return jsonify({
        'message': 'User created successfully',
        'user': user.serialize()
    }), 201

# Update a user
@user_bp.route('/<int:user_id>', methods=['PUT', 'PATCH'])
@jwt_required()
def update_user(user_id):
    """
    Update a user.
    
    Users can only update their own data unless they are admins.
    
    Args:
        user_id: ID of the user to update
        
    Request Body:
        email: (Optional) New email for the user
        password: (Optional) New password for the user
        first_name: (Optional) New first name for the user
        last_name: (Optional) New last name for the user
        is_active: (Optional) Whether the user is active
        is_admin: (Optional) Whether the user is an admin
        
    Returns:
        Updated user information
    """
    # Check permissions
    current_user_id = get_jwt_identity()
    current_user_obj = User.query.get(current_user_id)
    
    if not current_user_obj:
        return jsonify({'error': 'User not found'}), 404
    
    # Users can only update their own data unless they are admins
    is_admin = current_user_obj.is_admin
    is_self = (current_user_id == user_id)
    
    if not is_self and not is_admin:
        return jsonify({'error': 'Unauthorized'}), 403
    
    # Get user to update
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    data = request.get_json()
    
    # Update user fields
    if 'email' in data:
        # Check if email already exists
        if data['email'] != user.email and User.get_by_email(data['email']):
            return jsonify({'error': 'Email already exists'}), 409
        user.email = data['email']
    
    if 'password' in data:
        user.password = data['password']
    
    if 'first_name' in data:
        user.first_name = data['first_name']
    
    if 'last_name' in data:
        user.last_name = data['last_name']
    
    # Only admins can update these fields
    if is_admin:
        if 'is_active' in data:
            user.is_active = data['is_active']
        
        if 'is_admin' in data:
            user.is_admin = data['is_admin']
    
    # Update the timestamp
    user.updated_at = datetime.utcnow()
    
    # Save changes
    db.session.commit()
    
    return jsonify({
        'message': 'User updated successfully',
        'user': user.serialize()
    }), 200

# Delete a user
@user_bp.route('/<int:user_id>', methods=['DELETE'])
@jwt_required()
def delete_user(user_id):
    """
    Delete a user.
    
    Requires admin privileges.
    
    Args:
        user_id: ID of the user to delete
        
    Returns:
        Success message
    """
    # Check admin permissions
    current_user_id = get_jwt_identity()
    current_user_obj = User.query.get(current_user_id)
    
    if not current_user_obj or not current_user_obj.is_admin:
        return jsonify({'error': 'Admin privileges required'}), 403
    
    # Prevent deleting self
    if current_user_id == user_id:
        return jsonify({'error': 'Cannot delete your own account'}), 400
    
    # Get user to delete
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    # Delete user
    db.session.delete(user)
    db.session.commit()
    
    return jsonify({
        'message': 'User deleted successfully'
    }), 200 