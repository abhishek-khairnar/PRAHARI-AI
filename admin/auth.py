"""
PRAHARI-AI Admin Authentication & Authorization Layer
Handles password hashing (bcrypt), JWT generation/validation (pyjwt),
and Role-Based Access Control (RBAC) dependencies for FastAPI endpoints.
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

logger = logging.getLogger("PRAHARI-AUTH")

# Minimum 32-byte secret key for HS256 (RFC 7518 Section 3.2 compliance)
DEFAULT_SECRET = "prahari_secure_admin_jwt_secret_token_2026_key_production_grade"
SECRET_KEY = os.getenv("PRAHARI_SECRET_KEY", DEFAULT_SECRET)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 12

# HTTP Bearer scheme (handles Authorization: Bearer <token>)
security_bearer = HTTPBearer(auto_error=False)


def hash_password(plain_password: str) -> str:
    """Hashes a plaintext password using bcrypt with random salt."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(plain_password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plaintext password against a stored bcrypt hash."""
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception as e:
        logger.error(f"Password verification error: {e}")
        return False


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Generates a signed JWT bearer token containing subject, role, and expiration."""
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS))
    to_encode.update({"exp": expire, "iat": datetime.utcnow()})
    token = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return token


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Decodes and verifies a JWT token. Returns payload dict or None if invalid/expired."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("[AdminAuth] Token has expired")
        return None
    except jwt.InvalidTokenError as e:
        logger.warning(f"[AdminAuth] Invalid token: {e}")
        return None


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer)
) -> Dict[str, Any]:
    """
    FastAPI dependency that extracts and validates the JWT Bearer token.
    Denies access with 401 Unauthorized if missing, expired, or invalid.
    """
    token = None
    if credentials:
        token = credentials.credentials
    else:
        # Fallback to direct header extraction
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1].strip()

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please provide a valid Bearer token.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session token. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    username = payload["sub"]
    # Import db_manager dynamically to prevent circular imports
    from database import db_manager
    user = db_manager.get_admin_user_by_username(username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account no longer exists.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    if not user.get("is_active", 1):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account has been disabled. Please contact an administrator."
        )

    # Strip out password hash before returning user context
    safe_user = dict(user)
    safe_user.pop("password_hash", None)
    return safe_user


def require_role(allowed_roles: List[str]):
    """
    FastAPI dependency factory enforcing Role-Based Access Control (RBAC).
    Raises 403 Forbidden if current user role is not in allowed_roles.
    """
    async def role_checker(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
        user_role = current_user.get("role", "")
        if user_role not in allowed_roles:
            from database import db_manager
            db_manager.log_audit_event(
                actor_username=current_user.get("username", "UNKNOWN"),
                role=user_role,
                action="UNAUTHORIZED_ACCESS_ATTEMPT",
                resource_type="RBAC",
                result="DENIED",
                description=f"Attempted access without required role {allowed_roles}",
                actor_user_id=current_user.get("id")
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: Role '{user_role}' does not have sufficient privileges."
            )
        return current_user

    return role_checker
