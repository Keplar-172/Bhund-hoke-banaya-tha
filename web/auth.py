"""Authentication and authorization logic."""
from typing import Optional
from fastapi import Request, HTTPException, status
import bcrypt

from config import USERS_DB


class User:
    """Logged-in person. role: admin | user (shared viewer) | owner (own account)."""
    def __init__(self, username: str, role: str = "user", user_id: int | None = None):
        self.username = username
        self.role = role
        self.id = user_id
        self.is_admin = role == "admin" and user_id is None
        self.is_owner = role == "owner" and user_id is not None
        self.teams: dict = {}          # {tournament_id: owner_name} for owners


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
    user_id = request.session.get("user_id")
    if user_id:
        import accounts
        profile = accounts.get_profile(user_id)
        if profile is None:            # account deleted
            request.session.clear()
            return None
        u = User(username=profile["name"], role="owner", user_id=user_id)
        u.teams = {t["tournament_id"]: t["owner_name"] for t in profile["teams"]}
        return u
    username = request.session.get("username")
    role = request.session.get("role")
    if not username or role == "owner":
        return None
    return User(username=username, role=role)


def login_owner(request: Request, user_id: int) -> None:
    """Start an owner session (join link / re-login link)."""
    request.session.clear()
    request.session["user_id"] = user_id
    request.session["username"] = f"user-{user_id}"   # never a USERS_DB name
    request.session["role"] = "owner"


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
