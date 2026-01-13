# For MVP just placeholder – later add real aggregation
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from . import models, dependencies, database

router = APIRouter(prefix="/usage", tags=["usage"])

@router.get("/")
def get_usage_summary(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(dependencies.get_current_user)
):
    logs = db.query(models.UsageLog).filter(models.UsageLog.user_id == current_user.id).all()
    return [
        {
            "id": log.id,
            "provider": log.api_provider,
            "model": log.endpoint_or_model,
            "status": log.status_code,
            "latency_ms": log.latency_ms,
            "created_at": str(log.created_at)
        }
        for log in logs
    ]
