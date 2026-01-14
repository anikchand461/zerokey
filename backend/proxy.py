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


def _run_openrouter(api_key: str, body: dict):
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    return requests.post(url, headers=headers, json=body)


def _run_mistral(api_key: str, body: dict):
    url = "https://api.mistral.ai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    return requests.post(url, headers=headers, json=body)


def _run_together(api_key: str, body: dict):
    url = "https://api.together.xyz/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    return requests.post(url, headers=headers, json=body)


def _run_fireworks(api_key: str, body: dict):
    url = "https://api.fireworks.ai/inference/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    return requests.post(url, headers=headers, json=body)


def _run_anyscale(api_key: str, body: dict):
    url = "https://api.endpoints.anyscale.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    return requests.post(url, headers=headers, json=body)


def _run_deepinfra(api_key: str, body: dict):
    url = "https://api.deepinfra.com/v1/openai/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    return requests.post(url, headers=headers, json=body)


def _run_nebius(api_key: str, body: dict):
    url = "https://api.ai.nebius.cloud/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    return requests.post(url, headers=headers, json=body)


def _run_cohere(api_key: str, body: dict):
    url = "https://api.cohere.com/v1/chat"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    return requests.post(url, headers=headers, json=body)


def _run_ai21(api_key: str, body: dict):
    url = "https://api.ai21.com/studio/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    return requests.post(url, headers=headers, json=body)


def _run_perplexity(api_key: str, body: dict):
    url = "https://api.perplexity.ai/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    return requests.post(url, headers=headers, json=body)


def _run_deepseek(api_key: str, body: dict):
    url = "https://api.deepseek.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    return requests.post(url, headers=headers, json=body)


def _run_qwen(api_key: str, body: dict):
    url = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    return requests.post(url, headers=headers, json=body)


def _run_zhipu(api_key: str, body: dict):
    # For Zhipu (GLM), authentication uses JWT generated from API key (id.secret format)
    try:
        import jwt  # Requires PyJWT library
        id, secret = api_key.split('.')
        payload = {
            "api_key": id,
            "exp": int(time.time()) + 3600,
            "timestamp": int(time.time())
        }
        token = jwt.encode(payload, secret, algorithm="HS256")
    except Exception as e:
        raise HTTPException(400, f"Failed to generate JWT for Zhipu: {str(e)}")
    
    url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    return requests.post(url, headers=headers, json=body)


def _run_yi(api_key: str, body: dict):
    url = "https://api.lingyiwanwu.com/v1/chat/completions"  # Note: 01.AI is also known as Lingyi Wanwu
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    return requests.post(url, headers=headers, json=body)


def _run_grok(api_key: str, body: dict):
    url = "https://api.x.ai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    return requests.post(url, headers=headers, json=body)


def _run_aleph_alpha(api_key: str, body: dict):
    url = "https://api.aleph-alpha.com/complete"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    return requests.post(url, headers=headers, json=body)


def _run_replicate(api_key: str, body: dict):
    create_url = "https://api.replicate.com/v1/predictions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    create_resp = requests.post(create_url, headers=headers, json=body)
    if create_resp.status_code >= 400:
        return create_resp
    prediction = create_resp.json()
    prediction_id = prediction.get("id")
    if not prediction_id:
        raise HTTPException(500, "Failed to create prediction")
    
    while True:
        get_url = f"https://api.replicate.com/v1/predictions/{prediction_id}"
        get_resp = requests.get(get_url, headers=headers)
        if get_resp.status_code >= 400:
            return get_resp
        data = get_resp.json()
        status = data.get("status")
        if status in ["succeeded", "failed", "canceled"]:
            # Return the get_resp as the final response
            return get_resp
        time.sleep(1)


def _run_baseten(api_key: str, body: dict):
    url = "https://inference.baseten.co/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    return requests.post(url, headers=headers, json=body)


def _run_huggingface(api_key: str, body: dict):
    url = "https://api.huggingface.co/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    return requests.post(url, headers=headers, json=body)

# Note: For "modal", no fixed API endpoint as it's a deployment platform. 
# Users deploy custom endpoints, so proxy not implemented here.
# If you have a specific base URL, you can add it similarly.


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
    elif provider == "openrouter":
        resp = _run_openrouter(api_key, body)
    elif provider == "mistral":
        resp = _run_mistral(api_key, body)
    elif provider == "together":
        resp = _run_together(api_key, body)
    elif provider == "fireworks":
        resp = _run_fireworks(api_key, body)
    elif provider == "anyscale":
        resp = _run_anyscale(api_key, body)
    elif provider == "deepinfra":
        resp = _run_deepinfra(api_key, body)
    elif provider == "nebius":
        resp = _run_nebius(api_key, body)
    elif provider == "cohere":
        resp = _run_cohere(api_key, body)
    elif provider == "ai21":
        resp = _run_ai21(api_key, body)
    elif provider == "perplexity":
        resp = _run_perplexity(api_key, body)
    elif provider == "deepseek":
        resp = _run_deepseek(api_key, body)
    elif provider == "qwen":
        resp = _run_qwen(api_key, body)
    elif provider == "zhipu":
        resp = _run_zhipu(api_key, body)
    elif provider == "01ai":
        resp = _run_yi(api_key, body)
    elif provider == "grok":
        resp = _run_grok(api_key, body)
    elif provider == "aleph_alpha":
        resp = _run_aleph_alpha(api_key, body)
    elif provider == "replicate":
        resp = _run_replicate(api_key, body)
    elif provider == "baseten":
        resp = _run_baseten(api_key, body)
    elif provider == "huggingface":
        resp = _run_huggingface(api_key, body)
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