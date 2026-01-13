from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from jose import jwt
from datetime import datetime, timedelta, timezone

from . import models, database, config

router = APIRouter(prefix="/auth", tags=["auth"])

# Use argon2 – no need for truncation!
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

class RegisterRequest(BaseModel):
    username: str
    password: str
    email: str | None = None

@router.post("/register")
def register(
    request: RegisterRequest,
    db: Session = Depends(database.get_db)
):
    if db.query(models.User).filter(models.User.username == request.username).first():
        raise HTTPException(status_code=400, detail="Username already registered")

    # No truncation needed for argon2
    hashed_password = pwd_context.hash(request.password)

    user = models.User(
        username=request.username,
        hashed_password=hashed_password,
        email=request.email
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return {"message": "User created successfully", "username": request.username}


@router.post("/login")
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(database.get_db)
):
    user = db.query(models.User).filter(models.User.username == form_data.username).first()
    if not user or not pwd_context.verify(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Create JWT token
    access_token_expires = timedelta(minutes=config.JWT_EXPIRATION_MINUTES)
    access_token = jwt.encode(
        {
            "sub": str(user.id),  # must be string
            "exp": datetime.now(timezone.utc) + access_token_expires
        },
        config.JWT_SECRET,
        algorithm="HS256"
    )

    return {"access_token": access_token, "token_type": "bearer"}
