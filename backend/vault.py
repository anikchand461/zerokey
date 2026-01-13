from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List
from . import models, schemas, security, dependencies, database

router = APIRouter(prefix="/keys", tags=["vault"])

class ApiKeyCreate(BaseModel):
    provider: str
    key: str

class ApiKeyOut(BaseModel):
    id: int
    provider: str
    created_at: str

    class Config:
        from_attributes = True

@router.post("/", response_model=ApiKeyOut)
def add_key(
    key_in: ApiKeyCreate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(dependencies.get_current_user)
):
    encrypted = security.encrypt_api_key(key_in.key)
    db_key = models.ApiKey(
        user_id=current_user.id,
        api_provider=key_in.provider.lower(),
        encrypted_key=encrypted
    )
    db.add(db_key)
    db.commit()
    db.refresh(db_key)
    return {"id": db_key.id, "provider": db_key.api_provider, "created_at": str(db_key.created_at)}

@router.get("/", response_model=List[ApiKeyOut])
def list_keys(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(dependencies.get_current_user)
):
    keys = db.query(models.ApiKey).filter(models.ApiKey.user_id == current_user.id).all()
    return keys

@router.delete("/{key_id}")
def delete_key(
    key_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(dependencies.get_current_user)
):
    key = db.query(models.ApiKey).filter(
        models.ApiKey.id == key_id,
        models.ApiKey.user_id == current_user.id
    ).first()
    if not key:
        raise HTTPException(404, "Key not found")
    db.delete(key)
    db.commit()
    return {"detail": "Deleted"}
