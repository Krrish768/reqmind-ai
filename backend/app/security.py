"""Password hashing, JWT tokens and the current-user dependency."""
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from backend.app import models
from backend.app.config import settings
from backend.app.database import get_db

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer()


def hash_password(password: str) -> str:
    """Hash a password with bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Check a password against its bcrypt hash."""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(email: str, user_id: int) -> str:
    """Make a signed JWT that expires after ACCESS_TOKEN_EXPIRE_MINUTES.

    Args:
        email: Stored in the "sub" claim and used to find the user later.
        user_id: Stored for convenience.

    Returns:
        The encoded token.
    """
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": email, "user_id": user_id, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=ALGORITHM)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> models.User:
    """Return the user from the Bearer token, or answer 401."""
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Your session is not valid. Please log in again.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(credentials.credentials, settings.jwt_secret_key, algorithms=[ALGORITHM])
    except JWTError:
        raise unauthorized
    email = payload.get("sub")
    user = db.query(models.User).filter(models.User.email == email).first() if email else None
    if user is None:
        raise unauthorized
    return user
