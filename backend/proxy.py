import time
from datetime import datetime, timezone
import requests
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from . import database, dependencies, models, security

router = APIRouter(prefix="/proxy", tags=["proxy"])


def _ensure_not_expired(key: models.ApiKey) -> None:
    if key.expires_at:
        # Handle both naive and aware datetimes
        expires_at = key.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        
        if expires_at <= datetime.now(timezone.utc):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "API key has expired")


def _find_key_by_name(db: Session, provider: str, name_slug: str, user_id: int | None = None):
    q = db.query(models.ApiKey).filter(
        models.ApiKey.api_provider == provider,
        models.ApiKey.name_slug == name_slug,
    )
    if user_id:
        q = q.filter(models.ApiKey.user_id == user_id)
    return q.first()


def _run_openai(api_key: str, body: dict):
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    return requests.post(url, headers=headers, json=body)


def _run_groq(api_key: str, body: dict):
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    return requests.post(url, headers=headers, json=body)


def _run_anthropic(api_key: str, body: dict):
    url = "https://api.anthropic.com/v1/messages"
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }
    return requests.post(url, headers=headers, json=body)


def _run_gemini(api_key: str, body: dict):
    # Gemini uses a different format - model in URL
    model = body.get("model", "gemini-2.5-flash")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    return requests.post(url, json=body)


async def _proxy_request(provider: str, key_record: models.ApiKey, request: Request, db: Session):
    _ensure_not_expired(key_record)

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(400, "Invalid JSON body")

    api_key = security.decrypt_api_key(key_record.encrypted_key)

    start_time = time.time()
    if provider == "openai":
        resp = _run_openai(api_key, body)
    elif provider == "groq":
        resp = _run_groq(api_key, body)
    elif provider == "anthropic":
        resp = _run_anthropic(api_key, body)
    elif provider == "gemini":
        resp = _run_gemini(api_key, body)
    else:
        raise HTTPException(400, f"Proxy not implemented for {provider}")

    latency = int((time.time() - start_time) * 1000)

    usage_log = models.UsageLog(
        user_id=key_record.user_id,
        api_key_id=key_record.id,
        api_provider=provider,
        endpoint_or_model=body.get("model", "unknown"),
        status_code=resp.status_code,
        latency_ms=latency,
        total_tokens=resp.json().get("usage", {}).get("total_tokens", 0) if resp.ok else 0,
    )
    db.add(usage_log)
    db.commit()

    if resp.status_code >= 400:
        raise HTTPException(resp.status_code, resp.text)

    return resp.json()

@router.post("/{provider}/{name_slug}")
async def proxy_request_named(
    provider: str,
    name_slug: str,
    request: Request,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(dependencies.get_current_user),
):
    provider = provider.lower()
    key_record = _find_key_by_name(db, provider, name_slug, current_user.id)
    if not key_record:
        raise HTTPException(404, f"No {provider} key named {name_slug} found for user")

    return await _proxy_request(provider, key_record, request, db)


@router.post("/{provider}")
async def proxy_request_default(
    provider: str,
    request: Request,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(dependencies.get_current_user),
):
    provider = provider.lower()
    key_record = (
        db.query(models.ApiKey)
        .filter(models.ApiKey.user_id == current_user.id, models.ApiKey.api_provider == provider)
        .order_by(models.ApiKey.created_at.desc())
        .first()
    )
    if not key_record:
        raise HTTPException(404, f"No {provider} key found for user")

    return await _proxy_request(provider, key_record, request, db)


@router.post("/u/{provider}/{name_slug}")
async def proxy_unified(
    provider: str,
    name_slug: str,
    request: Request,
    db: Session = Depends(database.get_db),
    x_api_key: str | None = Header(default=None, convert_underscores=False),
    authorization: str | None = Header(default=None),
):
    provider = provider.lower()
    key_record = _find_key_by_name(db, provider, name_slug, user_id=None)
    if not key_record:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unified key not found")

    provided_key = x_api_key
    if not provided_key and authorization and authorization.lower().startswith("bearer "):
        provided_key = authorization.split(" ", 1)[1]

    if not provided_key:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing API key")

    stored_unified = security.decrypt_api_key(key_record.unified_key_encrypted)
    if stored_unified != provided_key:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid API key")

    return await _proxy_request(provider, key_record, request, db)
