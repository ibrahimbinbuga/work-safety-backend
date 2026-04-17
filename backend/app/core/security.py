"""Security helpers split from legacy auth module."""

from datetime import datetime, timedelta
from typing import Optional
import os

from dotenv import load_dotenv
from jose import JWTError, jwt
from passlib.context import CryptContext

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["argon2", "bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    truncated = password[:72]
    return pwd_context.hash(truncated)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        truncated = plain_password[:72]
        return pwd_context.verify(truncated, hashed_password)
    except Exception:
        return False


def create_access_token(
    user_id: int,
    email: str,
    role: str,
    company_code: str,
    expires_delta: Optional[timedelta] = None,
) -> str:
    if expires_delta is None:
        expires_delta = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {
        "user_id": user_id,
        "email": email,
        "role": role,
        "company_code": company_code,
        "exp": datetime.utcnow() + expires_delta,
    }
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str):
    from app.schemas.auth import TokenData

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: int = payload.get("user_id")
        email: str = payload.get("email")
        role: str = payload.get("role")
        company_code: str = payload.get("company_code")
        if user_id is None or email is None or role is None or company_code is None:
            return None
        return TokenData(
            user_id=user_id, email=email, role=role, company_code=company_code
        )
    except JWTError:
        return None

