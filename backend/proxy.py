import time
import requests
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from . import models, dependencies, database, security

router = APIRouter(prefix="/proxy", tags=["proxy"])

@router.post("/{provider}")
async def proxy_request(
    provider: str,
    request: Request,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(dependencies.get_current_user)
):
    provider = provider.lower()
    start_time = time.time()

    key_record = db.query(models.ApiKey).filter(
        models.ApiKey.user_id == current_user.id,
        models.ApiKey.api_provider == provider
    ).first()

    if not key_record:
        raise HTTPException(404, f"No {provider} key found for user")

    api_key = security.decrypt_api_key(key_record.encrypted_key)

    # Very simple OpenAI-style proxy – extend for others
    if provider == "openai":
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        try:
            body = await request.json()
        except:
            raise HTTPException(400, "Invalid JSON body")

        resp = requests.post(url, headers=headers, json=body)
        latency = int((time.time() - start_time) * 1000)

        # Minimal usage logging (you should parse usage from response if available)
        usage_log = models.UsageLog(
            user_id=current_user.id,
            api_provider=provider,
            endpoint_or_model=body.get("model", "unknown"),
            status_code=resp.status_code,
            latency_ms=latency,
            # tokens would require parsing resp.json() → .usage
        )
        db.add(usage_log)
        db.commit()

        if resp.status_code >= 400:
            raise HTTPException(resp.status_code, resp.text)

        return resp.json()

    raise HTTPException(400, f"Proxy not implemented for {provider}")
