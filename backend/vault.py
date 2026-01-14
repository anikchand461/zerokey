import re
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from . import database, dependencies, models, schemas, security, provider_detection

router = APIRouter(prefix="/keys", tags=["vault"])


def _slugify(value: str) -> str:
    clean = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower())
    return clean.strip("-") or "key"


def _mask_api_key(key: str) -> str:
    """Mask API key showing only first 4 and last 4 characters."""
    if len(key) <= 8:
        return "****"
    return f"{key[:4]}****{key[-4:]}"


class ApiKeyCreate(BaseModel):
    name: str
    key: str
    expires_at: Optional[datetime] = None


@router.post("/", response_model=schemas.ApiKeyOut, status_code=status.HTTP_201_CREATED)
def add_key(
    key_in: ApiKeyCreate,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(dependencies.get_current_user),
):
    # Auto-detect provider from API key
    try:
        provider = provider_detection.detect_provider(key_in.key)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    provider_slug = _slugify(provider)
    name_slug = _slugify(key_in.name)

    existing = (
        db.query(models.ApiKey)
        .filter(
            models.ApiKey.user_id == current_user.id,
            models.ApiKey.api_provider == provider_slug,
            models.ApiKey.name_slug == name_slug,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="Key name already exists for this provider")

    unified_api_key_plain = f"apikey-{provider_slug}-{name_slug}"
    expires_at = key_in.expires_at
    if expires_at is not None and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    db_key = models.ApiKey(
        user_id=current_user.id,
        api_provider=provider_slug,
        name=key_in.name.strip(),
        name_slug=name_slug,
        encrypted_key=security.encrypt_api_key(key_in.key),
        unified_key_encrypted=security.encrypt_api_key(unified_api_key_plain),
        unified_endpoint=f"/proxy/u/{provider_slug}/{name_slug}",
        expires_at=expires_at,
    )

    db.add(db_key)
    db.commit()
    db.refresh(db_key)

    decrypted_key = security.decrypt_api_key(db_key.encrypted_key)

    return schemas.ApiKeyOut(
        id=db_key.id,
        provider=db_key.api_provider,
        name=db_key.name,
        created_at=db_key.created_at,
        expires_at=db_key.expires_at,
        api_key=_mask_api_key(decrypted_key),
        unified_api_key=unified_api_key_plain,
        unified_endpoint=db_key.unified_endpoint,
    )


@router.get("/", response_model=List[schemas.ApiKeyOut])
def list_keys(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(dependencies.get_current_user),
):
    keys = (
        db.query(models.ApiKey)
        .filter(models.ApiKey.user_id == current_user.id)
        .order_by(models.ApiKey.created_at.desc())
        .all()
    )

    return [
        schemas.ApiKeyOut(
            id=k.id,
            provider=k.api_provider,
            name=k.name,
            created_at=k.created_at,
            expires_at=k.expires_at,
            api_key=_mask_api_key(security.decrypt_api_key(k.encrypted_key)),
            unified_api_key=security.decrypt_api_key(k.unified_key_encrypted),
            unified_endpoint=k.unified_endpoint,
        )
        for k in keys
    ]


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_key(
    key_id: int,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(dependencies.get_current_user),
):
    key = (
        db.query(models.ApiKey)
        .filter(models.ApiKey.id == key_id, models.ApiKey.user_id == current_user.id)
        .first()
    )

    if not key:
        raise HTTPException(status_code=404, detail="Key not found or not owned by you")

    # Optionally cascade delete usage entries for this key
    db.query(models.UsageLog).filter(models.UsageLog.api_key_id == key_id).delete()

    db.delete(key)
    db.commit()
    return None
