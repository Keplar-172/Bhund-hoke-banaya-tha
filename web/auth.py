"""Authentication and authorization logic."""
from typing import Optional
from fastapi import Request, HTTPException, status
import bcrypt

from config import USERS_DB


class User:
    """Simple user model."""
    def __init__(self, username: str, role: str = "user"):
        self.username = username
        self.role = role
        self.is_admin = role == "admin"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return bcrypt.checkpw(
        plain_password.encode('utf-8'),
        hashed_password.encode('utf-8')
    )


def get_password_hash(password: str) -> str:
    """Hash a password."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')


def authenticate_user(username: str, password: str) -> Optional[User]:
    """Authenticate a user by username and password."""
    user_data = USERS_DB.get(username)
    if not user_data:
        return None
    if not verify_password(password, user_data["password_hash"]):
        return None
    return User(username=username, role=user_data.get("role", "user"))


def get_current_user(request: Request) -> Optional[User]:
    """Get the current authenticated user from session."""
    username = request.session.get("username")
    role = request.session.get("role")
    if not username:
        return None
    return User(username=username, role=role)


def require_auth(request: Request) -> User:
    """Dependency that requires authentication."""
    user = get_current_user(request)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    return user


def require_admin(request: Request) -> User:
    """Dependency that requires admin role."""
    user = require_auth(request)
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user
