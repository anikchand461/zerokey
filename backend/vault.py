from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from pydantic import BaseModel
from datetime import datetime

from . import models, security, dependencies, database

router = APIRouter(prefix="/keys", tags=["vault"])

# Request for adding key
class ApiKeyCreate(BaseModel):
    provider: str
    key: str

# Safe response model
class ApiKeyOut(BaseModel):
    id: int
    provider: str               # renamed from api_provider
    created_at: datetime
    key_preview: str            # last 4 chars

    class Config:
        from_attributes = True

@router.post("/", response_model=ApiKeyOut, status_code=status.HTTP_201_CREATED)
def add_key(
    key_in: ApiKeyCreate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(dependencies.get_current_user)
):
    encrypted = security.encrypt_api_key(key_in.key)

    db_key = models.ApiKey(
        user_id=current_user.id,
        api_provider=key_in.provider.lower().strip(),
        encrypted_key=encrypted
    )

    db.add(db_key)
    db.commit()
    db.refresh(db_key)

    # Transform to match ApiKeyOut (this fixes the validation error)
    return ApiKeyOut(
        id=db_key.id,
        provider=db_key.api_provider,
        created_at=db_key.created_at,
        key_preview=db_key.encrypted_key[-4:] if db_key.encrypted_key else "****"
    )

@router.get("/", response_model=List[ApiKeyOut])
def list_keys(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(dependencies.get_current_user)
):
    keys = (
        db.query(models.ApiKey)
        .filter(models.ApiKey.user_id == current_user.id)
        .order_by(models.ApiKey.created_at.desc())
        .all()
    )

    # Transform each key to ApiKeyOut
    return [
        ApiKeyOut(
            id=k.id,
            provider=k.api_provider,
            created_at=k.created_at,
            key_preview=k.encrypted_key[-4:] if k.encrypted_key else "****"
        )
        for k in keys
    ]

@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_key(
    key_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(dependencies.get_current_user)
):
    key = (
        db.query(models.ApiKey)
        .filter(
            models.ApiKey.id == key_id,
            models.ApiKey.user_id == current_user.id
        )
        .first()
    )

    if not key:
        raise HTTPException(status_code=404, detail="Key not found or not owned by you")

    db.delete(key)
    db.commit()
    return None
