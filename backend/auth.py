# backend/auth.py
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
import os
from dotenv import load_dotenv
from config import is_admin_company_code

# Load environment variables
load_dotenv()

# Configuration
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ===== Pydantic Models =====

class Token(BaseModel):
    access_token: str
    token_type: str
    user_id: int
    email: str
    role: str
    company_code: str


class TokenData(BaseModel):
    user_id: Optional[int] = None
    email: Optional[str] = None
    role: Optional[str] = None
    company_code: Optional[str] = None


class LoginRequest(BaseModel):
    email: str
    password: str
    company_code: str


class UserCreate(BaseModel):
    email: str
    password: str
    company_code: str
    role: str = "user"  # Default role


class UserResponse(BaseModel):
    id: int
    email: str
    role: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class CompanyResponse(BaseModel):
    id: int
    code: str
    name: str
    created_at: datetime

    class Config:
        from_attributes = True


# ===== Admin Code Utilities =====

def is_admin(company_code: str) -> bool:
    """Check if a company code is an admin code."""
    return is_admin_company_code(company_code)


# ===== Password Hashing Functions =====

def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


# ===== JWT Token Functions =====

def create_access_token(
    user_id: int,
    email: str,
    role: str,
    company_code: str,
    expires_delta: Optional[timedelta] = None
) -> str:
    """Create a JWT access token."""
    if expires_delta is None:
        expires_delta = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode = {
        "user_id": user_id,
        "email": email,
        "role": role,
        "company_code": company_code,
        "exp": datetime.utcnow() + expires_delta
    }
    
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[TokenData]:
    """Decode and validate a JWT access token."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: int = payload.get("user_id")
        email: str = payload.get("email")
        role: str = payload.get("role")
        company_code: str = payload.get("company_code")
        
        if user_id is None or email is None or role is None or company_code is None:
            return None
        
        return TokenData(user_id=user_id, email=email, role=role, company_code=company_code)
    except JWTError:
        return None
