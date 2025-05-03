#!/usr/bin/env python
"""
Management script for the application.

Provides commands to manage the application, such as database migrations.
"""
import sys
import os
import click
from flask.cli import FlaskGroup
from dotenv import load_dotenv

from aurora_backend_llm.app import create_app

# Load environment variables from .env file
load_dotenv()

def _create_app(script_info=None):
    return create_app()

@click.group(cls=FlaskGroup, create_app=_create_app)
def cli():
    """Management script for the application."""
    pass

@cli.command("init-db")
def init_db():
    """Initialize the database."""
    from flask import current_app
    from aurora_backend_llm.db import db, User
    from flask_migrate import upgrade

    click.echo("Creating database tables...")
    
    # Run migrations
    with current_app.app_context():
        upgrade()
    
    click.echo("Database tables created successfully!")
    
    # Check if admin user exists
    admin_username = os.environ.get('ADMIN_USERNAME', 'admin')
    admin_email = os.environ.get('ADMIN_EMAIL', 'admin@example.com')
    admin_password = os.environ.get('ADMIN_PASSWORD', 'admin123')
    
    with current_app.app_context():
        if not User.get_by_username(admin_username):
            click.echo(f"Creating admin user '{admin_username}'...")
            
            admin_user = User(
                username=admin_username,
                email=admin_email,
                is_active=True,
                is_admin=True
            )
            admin_user.password = admin_password
            
            db.session.add(admin_user)
            db.session.commit()
            
            click.echo("Admin user created successfully!")
        else:
            click.echo(f"Admin user '{admin_username}' already exists.")

@cli.command("create-user")
@click.option('--username', prompt=True, help='Username for the new user')
@click.option('--email', prompt=True, help='Email for the new user')
@click.option('--password', prompt=True, hide_input=True, confirmation_prompt=True, help='Password for the new user')
@click.option('--admin', is_flag=True, default=False, help='Make the user an admin')
def create_user(username, email, password, admin):
    """Create a new user."""
    from aurora_backend_llm.db import db, User
    
    with create_app().app_context():
        if User.get_by_username(username):
            click.echo(f"User with username '{username}' already exists.")
            return
        
        if User.get_by_email(email):
            click.echo(f"User with email '{email}' already exists.")
            return
        
        user = User(
            username=username,
            email=email,
            is_active=True,
            is_admin=admin
        )
        user.password = password
        
        db.session.add(user)
        db.session.commit()
        
        click.echo(f"User '{username}' created successfully!")

if __name__ == '__main__':
    cli() 