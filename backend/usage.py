from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from . import database, dependencies, models

router = APIRouter(prefix="/usage", tags=["usage"])


def _serialize_log(log: models.UsageLog):
    return {
        "id": log.id,
        "api_key_id": log.api_key_id,
        "provider": log.api_provider,
        "model": log.endpoint_or_model,
        "status": log.status_code,
        "latency_ms": log.latency_ms,
        "total_tokens": log.total_tokens,
        "created_at": str(log.created_at),
    }


@router.get("/")
def get_usage_summary(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(dependencies.get_current_user),
):
    logs = db.query(models.UsageLog).filter(models.UsageLog.user_id == current_user.id).all()
    return [_serialize_log(log) for log in logs]


@router.get("/{key_id}")
def get_usage_for_key(
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
        raise HTTPException(status_code=404, detail="API key not found")

    logs = (
        db.query(models.UsageLog)
        .filter(models.UsageLog.user_id == current_user.id, models.UsageLog.api_key_id == key_id)
        .order_by(models.UsageLog.created_at.desc())
        .all()
    )
    return {
        "key": {
            "id": key.id,
            "name": key.name,
            "provider": key.api_provider,
        },
        "logs": [_serialize_log(log) for log in logs],
    }
