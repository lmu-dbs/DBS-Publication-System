from jose import JWTError, jwt
from datetime import datetime, timedelta
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from typing import Optional
import os
from dotenv import load_dotenv


from .login_tracker import login_tracker


# Load environment variables from .env file if it exists
load_dotenv()


from ..models.database import get_db
from ..models.models import User
from ..schemas.schemas import TokenData


# Configuration for JWT
SECRET_KEY = os.getenv("SECRET_KEY", "f8e9a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours

# Admin credentials - read from environment variables
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin")  # This should be changed in production

# Password context for hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 scheme for token authentication
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)


def get_user(db: Session, username: str):
    # Query the database for the user
    user = db.query(User).filter(User.username == username).first()
    
    # Create admin user if it doesn't exist and this is the admin username from environment
    if not user and username == ADMIN_USERNAME:
        user = User(
            username=ADMIN_USERNAME,
            email="admin@example.com",
            hashed_password=get_password_hash(ADMIN_PASSWORD),
            is_active=1
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    
    return user


def authenticate_user(db: Session, username: str, password: str):
    # Check if the user is locked out due to too many failed attempts
    is_locked, seconds_remaining = login_tracker.is_locked_out(username)
    if is_locked:
        minutes_remaining = seconds_remaining // 60
        seconds = seconds_remaining % 60
        time_msg = f"{minutes_remaining}m {seconds}s" if minutes_remaining else f"{seconds_remaining}s"
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many failed login attempts. Please try again in {time_msg}."
        )
    
    user = get_user(db, username)
    if not user:
        # Record failed attempt for non-existent users too
        login_tracker.record_failed_attempt(username)
        return False
        
    # Verify the password
    if not verify_password(password, user.hashed_password):
        # For backward compatibility with admin user
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            # Update the password if it was changed
            user.hashed_password = get_password_hash(password)
            db.commit()
            # Reset any failed login attempts
            login_tracker.reset_attempts(username)
            return user
            
        # Record failed login attempt
        login_tracker.record_failed_attempt(username)
        return False
    
    # Reset failed login attempts on successful login
    login_tracker.reset_attempts(username)
    return user


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception
        
    user = get_user(db, username=token_data.username)
    if user is None:
        raise credentials_exception
    return user


async def get_current_active_user(current_user: User = Depends(get_current_user)):
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user
