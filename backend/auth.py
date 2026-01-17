from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import RedirectResponse, JSONResponse, HTMLResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from jose import jwt
from datetime import datetime, timedelta, timezone
import requests
import os

from . import models, database, config, dependencies

router = APIRouter(prefix="/auth", tags=["auth"])

# Use argon2 – no need for truncation!
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

class RegisterRequest(BaseModel):
    username: str
    password: str
    email: str | None = None


class PasswordUpdateRequest(BaseModel):
    old_password: str
    new_password: str


PROFILE_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend", "static", "images")


def _get_local_profile_images():
    if not os.path.isdir(PROFILE_DIR):
        return []
    files = [f for f in os.listdir(PROFILE_DIR) if f.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp"))]
    files.sort()
    return files

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
        email=request.email,
        auth_method="jwt"
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


@router.get("/me")
def get_me(
    current_user: models.User = Depends(dependencies.get_current_user),
):
    avatar_url = None
    if current_user.auth_method == "github" and current_user.github_username:
        avatar_url = f"https://avatars.githubusercontent.com/{current_user.github_username}"
    elif current_user.auth_method == "gitlab" and current_user.gitlab_username:
        avatar_url = f"https://gitlab.com/{current_user.gitlab_username}.png"
    elif current_user.auth_method == "bitbucket" and current_user.bitbucket_username:
        avatar_url = f"https://bitbucket.org/account/{current_user.bitbucket_username}/avatar/"

    # Provide local avatar paths; frontend will choose any default/random
    local_avatars = [f"/static/images/{name}" for name in _get_local_profile_images()]

    # Build explicit image paths
    profile_images = {}
    for i, name in enumerate(_get_local_profile_images()):
        profile_images[f"profile_image_{i}"] = f"/static/images/{name}"

    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "auth_method": current_user.auth_method,
        "github_username": current_user.github_username,
        "gitlab_username": current_user.gitlab_username,
        "bitbucket_username": current_user.bitbucket_username,
        "created_at": current_user.created_at,
        "avatar_url": avatar_url,
        "local_avatars": local_avatars,
        **profile_images,  # Spread explicit image paths
    }


@router.post("/password")
def update_password(
    payload: PasswordUpdateRequest,
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(dependencies.get_current_user),
):
    if current_user.auth_method != "jwt" or not current_user.hashed_password:
        raise HTTPException(status_code=400, detail="Password update available only for JWT users")

    if not pwd_context.verify(payload.old_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Old password is incorrect")

    current_user.hashed_password = pwd_context.hash(payload.new_password)
    db.commit()

    return {"message": "Password updated successfully"}


# ────────────────────────────────────────────────
# GitHub OAuth Routes
# ────────────────────────────────────────────────

@router.get("/github/login")
def github_login(state: str | None = None):
    """Redirect user to GitHub for authentication"""
    if not config.GITHUB_CLIENT_ID or not config.GITHUB_CLIENT_SECRET:
        raise HTTPException(400, detail="GitHub OAuth not configured. Set GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET in .env")
    
    github_auth_url = (
        f"https://github.com/login/oauth/authorize?"
        f"client_id={config.GITHUB_CLIENT_ID}&"
        f"redirect_uri={config.GITHUB_REDIRECT_URI}&"
        f"scope=user:email"
    )
    if state:
        github_auth_url += f"&state={state}"
    return RedirectResponse(url=github_auth_url)


@router.get("/github/callback")
def github_callback(
    code: str = None, 
    error: str = None, 
    state: str | None = None,
    request = None,
    db: Session = Depends(database.get_db)
):
    """Handle GitHub OAuth callback"""
    # Handle GitHub error response
    if error:
        error_desc = f"GitHub+error:+{error}"
        return RedirectResponse(url=f"/static/index.html?error={error_desc}")
    
    if not code:
        return RedirectResponse(url="/static/index.html?error=No+authorization+code+received")
    
    if not config.GITHUB_CLIENT_ID or not config.GITHUB_CLIENT_SECRET:
        return RedirectResponse(url="/static/index.html?error=GitHub+OAuth+not+configured")
    
    try:
        print(f"[GitHub OAuth] Exchanging code: {code[:20]}...")
        
        # Exchange code for access token
        token_response = requests.post(
            "https://github.com/login/oauth/access_token",
            json={
                "client_id": config.GITHUB_CLIENT_ID,
                "client_secret": config.GITHUB_CLIENT_SECRET,
                "code": code
            },
            headers={"Accept": "application/json"}
        )
        
        print(f"[GitHub OAuth] Token response status: {token_response.status_code}")
        token_response.raise_for_status()
        token_data = token_response.json()
        
        if "error" in token_data:
            error_msg = token_data.get("error_description", token_data["error"])
            print(f"[GitHub OAuth] Error: {error_msg}")
            return RedirectResponse(url=f"/static/index.html?error=GitHub+error:+{error_msg}")
        
        if "access_token" not in token_data:
            print(f"[GitHub OAuth] No access token in response: {token_data}")
            return RedirectResponse(url="/static/index.html?error=Failed+to+get+access+token")
        
        github_token = token_data["access_token"]
        print(f"[GitHub OAuth] Got access token: {github_token[:20]}...")
        
        # Get user info from GitHub
        user_response = requests.get(
            "https://api.github.com/user",
            headers={
                "Authorization": f"Bearer {github_token}",
                "Accept": "application/json"
            }
        )
        user_response.raise_for_status()
        github_user = user_response.json()
        print(f"[GitHub OAuth] Got user: {github_user['login']}")
        
        # Get email from GitHub
        email_response = requests.get(
            "https://api.github.com/user/emails",
            headers={
                "Authorization": f"Bearer {github_token}",
                "Accept": "application/json"
            }
        )
        email_response.raise_for_status()
        emails = email_response.json()
        primary_email = next((e["email"] for e in emails if e.get("primary")), github_user.get("email"))
        print(f"[GitHub OAuth] Got email: {primary_email}")
        
        # Check if user exists
        user = db.query(models.User).filter(
            models.User.github_id == str(github_user["id"])
        ).first()
        
        if not user:
            print(f"[GitHub OAuth] Creating new user: {github_user['login']}")
            # Create new user
            user = models.User(
                username=github_user["login"],
                github_id=str(github_user["id"]),
                github_username=github_user["login"],
                email=primary_email,
                auth_method="github",
                hashed_password=None  # No password for OAuth users
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            print(f"[GitHub OAuth] User created with ID: {user.id}")
        else:
            print(f"[GitHub OAuth] User exists with ID: {user.id}")
            # Update existing user's email if needed
            if primary_email and user.email != primary_email:
                user.email = primary_email
                db.commit()
        
        # Create JWT token
        access_token_expires = timedelta(minutes=config.JWT_EXPIRATION_MINUTES)
        access_token = jwt.encode(
            {
                "sub": str(user.id),
                "exp": datetime.now(timezone.utc) + access_token_expires
            },
            config.JWT_SECRET,
            algorithm="HS256"
        )
        
        print(f"[GitHub OAuth] Generated JWT token for user {user.id}")
        
        # If the request originated from the CLI, show the token explicitly for pasting back
        if state == "cli":
            from fastapi.responses import HTMLResponse
            html = f"""
            <html>
                <head>
                    <title>Zerokey CLI Login</title>
                    <style>
                        body {{ font-family: Arial, sans-serif; max-width: 720px; margin: 40px auto; padding: 0 16px; }}
                        pre {{ background: #0f172a; color: #e2e8f0; padding: 12px; border-radius: 8px; overflow-x: auto; }}
                        button {{ background: #0ea5e9; color: #0b1120; border: none; padding: 10px 14px; border-radius: 6px; cursor: pointer; font-size: 14px; }}
                        button:hover {{ background: #38bdf8; }}
                        .card {{ border: 1px solid #e2e8f0; border-radius: 10px; padding: 18px; }}
                    </style>
                </head>
                <body>
                    <div class="card">
                        <h2>CLI login successful</h2>
                        <p>Copy this JWT and paste it back into your terminal when prompted.</p>
                        <pre id="token">{access_token}</pre>
                        <button onclick="navigator.clipboard.writeText(document.getElementById('token').textContent)">Copy token</button>
                        <p style="margin-top:12px;">Keep this token secret. You can now close this tab or head to the dashboard.</p>
                        <p><a href="/static/dashboard.html">Open dashboard</a></p>
                    </div>
                </body>
            </html>
            """
            return HTMLResponse(html)

        # Default web flow: persist token in localStorage then send to dashboard
        from fastapi.responses import HTMLResponse
        html = f"""
        <html>
            <head>
                <script>
                    localStorage.setItem('access_token', '{access_token}');
                    window.location.href = '/static/dashboard.html';
                </script>
            </head>
            <body>
                <p>Redirecting to dashboard...</p>
            </body>
        </html>
        """
        return HTMLResponse(html)
        
    except requests.exceptions.RequestException as e:
        print(f"[GitHub OAuth] Request error: {str(e)}")
        error_msg = f"API+error:+{str(e)[:50]}"
        return RedirectResponse(url=f"/static/index.html?error={error_msg}")
    except Exception as e:
        print(f"[GitHub OAuth] Unexpected error: {str(e)}")
        error_msg = f"Error:+{str(e)[:50]}"
        return RedirectResponse(url=f"/static/index.html?error={error_msg}")


# ────────────────────────────────────────────────
# GitLab OAuth Routes
# ────────────────────────────────────────────────

@router.get("/gitlab/login")
def gitlab_login(state: str | None = None):
    """Redirect user to GitLab for authentication"""
    if not config.GITLAB_CLIENT_ID or not config.GITLAB_CLIENT_SECRET:
        raise HTTPException(400, detail="GitLab OAuth not configured. Set GITLAB_CLIENT_ID and GITLAB_CLIENT_SECRET in .env")
    
    gitlab_auth_url = (
        f"https://gitlab.com/oauth/authorize?"
        f"client_id={config.GITLAB_CLIENT_ID}&"
        f"redirect_uri={config.GITLAB_REDIRECT_URI}&"
        f"response_type=code&"
        f"scope=read_user+api"
    )
    if state:
        gitlab_auth_url += f"&state={state}"
    return RedirectResponse(url=gitlab_auth_url)


@router.get("/gitlab/callback")
def gitlab_callback(
    code: str = None, 
    error: str = None, 
    state: str | None = None,
    request = None,
    db: Session = Depends(database.get_db)
):
    """Handle GitLab OAuth callback"""
    # Handle GitLab error response
    if error:
        error_desc = f"GitLab+error:+{error}"
        return RedirectResponse(url=f"/static/index.html?error={error_desc}")
    
    if not code:
        return RedirectResponse(url="/static/index.html?error=No+authorization+code+received")
    
    if not config.GITLAB_CLIENT_ID or not config.GITLAB_CLIENT_SECRET:
        return RedirectResponse(url="/static/index.html?error=GitLab+OAuth+not+configured")
    
    try:
        print(f"[GitLab OAuth] Exchanging code: {code[:20]}...")
        
        # Exchange code for access token
        token_response = requests.post(
            "https://gitlab.com/oauth/token",
            json={
                "client_id": config.GITLAB_CLIENT_ID,
                "client_secret": config.GITLAB_CLIENT_SECRET,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": config.GITLAB_REDIRECT_URI
            },
            headers={"Accept": "application/json"}
        )
        
        print(f"[GitLab OAuth] Token response status: {token_response.status_code}")
        token_response.raise_for_status()
        token_data = token_response.json()
        
        if "error" in token_data:
            error_msg = token_data.get("error_description", token_data["error"])
            print(f"[GitLab OAuth] Error: {error_msg}")
            return RedirectResponse(url=f"/static/index.html?error=GitLab+error:+{error_msg}")
        
        if "access_token" not in token_data:
            print(f"[GitLab OAuth] No access token in response: {token_data}")
            return RedirectResponse(url="/static/index.html?error=Failed+to+get+access+token")
        
        gitlab_token = token_data["access_token"]
        print(f"[GitLab OAuth] Got access token: {gitlab_token[:20]}...")
        
        # Get user info from GitLab
        user_response = requests.get(
            "https://gitlab.com/api/v4/user",
            headers={
                "Authorization": f"Bearer {gitlab_token}",
                "Accept": "application/json"
            }
        )
        user_response.raise_for_status()
        gitlab_user = user_response.json()
        print(f"[GitLab OAuth] Got user: {gitlab_user['username']}")
        
        # Check if user exists
        user = db.query(models.User).filter(
            models.User.gitlab_id == str(gitlab_user["id"])
        ).first()
        
        if not user:
            print(f"[GitLab OAuth] Creating new user: {gitlab_user['username']}")
            # Create new user
            user = models.User(
                username=gitlab_user["username"],
                gitlab_id=str(gitlab_user["id"]),
                gitlab_username=gitlab_user["username"],
                email=gitlab_user.get("email"),
                auth_method="gitlab",
                hashed_password=None  # No password for OAuth users
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            print(f"[GitLab OAuth] User created with ID: {user.id}")
        else:
            print(f"[GitLab OAuth] User exists with ID: {user.id}")
            # Update existing user's email if needed
            if gitlab_user.get("email") and user.email != gitlab_user.get("email"):
                user.email = gitlab_user.get("email")
                db.commit()
        
        # Create JWT token
        access_token_expires = timedelta(minutes=config.JWT_EXPIRATION_MINUTES)
        access_token = jwt.encode(
            {
                "sub": str(user.id),
                "exp": datetime.now(timezone.utc) + access_token_expires
            },
            config.JWT_SECRET,
            algorithm="HS256"
        )
        
        print(f"[GitLab OAuth] Generated JWT token for user {user.id}")
        
        # If the request originated from the CLI, show the token explicitly for pasting back
        if state == "cli":
            from fastapi.responses import HTMLResponse
            html = f"""
            <html>
                <head>
                    <title>Zerokey CLI Login</title>
                    <style>
                        body {{ font-family: Arial, sans-serif; max-width: 720px; margin: 40px auto; padding: 0 16px; }}
                        pre {{ background: #0f172a; color: #e2e8f0; padding: 12px; border-radius: 8px; overflow-x: auto; }}
                        button {{ background: #0ea5e9; color: #0b1120; border: none; padding: 10px 14px; border-radius: 6px; cursor: pointer; font-size: 14px; }}
                        button:hover {{ background: #38bdf8; }}
                        .card {{ border: 1px solid #e2e8f0; border-radius: 10px; padding: 18px; }}
                    </style>
                </head>
                <body>
                    <div class="card">
                        <h2>CLI login successful</h2>
                        <p>Copy this JWT and paste it back into your terminal when prompted.</p>
                        <pre id="token">{access_token}</pre>
                        <button onclick="navigator.clipboard.writeText(document.getElementById('token').textContent)">Copy token</button>
                        <p style="margin-top:12px;">Keep this token secret. You can now close this tab or head to the dashboard.</p>
                        <p><a href="/static/dashboard.html">Open dashboard</a></p>
                    </div>
                </body>
            </html>
            """
            return HTMLResponse(html)

        # Default web flow: persist token in localStorage then send to dashboard
        from fastapi.responses import HTMLResponse
        html = f"""
        <html>
            <head>
                <script>
                    localStorage.setItem('access_token', '{access_token}');
                    window.location.href = '/static/dashboard.html';
                </script>
            </head>
            <body>
                <p>Redirecting to dashboard...</p>
            </body>
        </html>
        """
        return HTMLResponse(html)
        
    except requests.exceptions.RequestException as e:
        print(f"[GitLab OAuth] Request error: {str(e)}")
        error_msg = f"API+error:+{str(e)[:50]}"
        return RedirectResponse(url=f"/static/index.html?error={error_msg}")
    except Exception as e:
        print(f"[GitLab OAuth] Unexpected error: {str(e)}")
        error_msg = f"Error:+{str(e)[:50]}"
        return RedirectResponse(url=f"/static/index.html?error={error_msg}")


# ────────────────────────────────────────────────
# Bitbucket OAuth Routes
# ────────────────────────────────────────────────

@router.get("/bitbucket/login")
def bitbucket_login(state: str | None = None):
    """Redirect user to Bitbucket for authentication"""
    if not config.BITBUCKET_CLIENT_ID or not config.BITBUCKET_CLIENT_SECRET:
        raise HTTPException(400, detail="Bitbucket OAuth not configured. Set BITBUCKET_CLIENT_ID and BITBUCKET_CLIENT_SECRET in .env")
    
    bitbucket_auth_url = (
        f"https://bitbucket.org/site/oauth2/authorize?"
        f"client_id={config.BITBUCKET_CLIENT_ID}&"
        f"redirect_uri={config.BITBUCKET_REDIRECT_URI}&"
        f"response_type=code&"
        f"scope=account:read_public"
    )
    if state:
        bitbucket_auth_url += f"&state={state}"
    return RedirectResponse(url=bitbucket_auth_url)


@router.get("/bitbucket/callback")
def bitbucket_callback(
    code: str = None, 
    error: str = None, 
    state: str | None = None,
    request = None,
    db: Session = Depends(database.get_db)
):
    """Handle Bitbucket OAuth callback"""
    # Handle Bitbucket error response
    if error:
        error_desc = f"Bitbucket+error:+{error}"
        return RedirectResponse(url=f"/static/index.html?error={error_desc}")
    
    if not code:
        return RedirectResponse(url="/static/index.html?error=No+authorization+code+received")
    
    if not config.BITBUCKET_CLIENT_ID or not config.BITBUCKET_CLIENT_SECRET:
        return RedirectResponse(url="/static/index.html?error=Bitbucket+OAuth+not+configured")
    
    try:
        print(f"[Bitbucket OAuth] Exchanging code: {code[:20]}...")
        
        # Exchange code for access token
        token_response = requests.post(
            "https://bitbucket.org/site/oauth2/access_token",
            auth=(config.BITBUCKET_CLIENT_ID, config.BITBUCKET_CLIENT_SECRET),
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": config.BITBUCKET_REDIRECT_URI
            },
            headers={"Accept": "application/json"}
        )
        
        print(f"[Bitbucket OAuth] Token response status: {token_response.status_code}")
        token_response.raise_for_status()
        token_data = token_response.json()
        
        if "error" in token_data:
            error_msg = token_data.get("error_description", token_data["error"])
            print(f"[Bitbucket OAuth] Error: {error_msg}")
            return RedirectResponse(url=f"/static/index.html?error=Bitbucket+error:+{error_msg}")
        
        if "access_token" not in token_data:
            print(f"[Bitbucket OAuth] No access token in response: {token_data}")
            return RedirectResponse(url="/static/index.html?error=Failed+to+get+access+token")
        
        bitbucket_token = token_data["access_token"]
        print(f"[Bitbucket OAuth] Got access token: {bitbucket_token[:20]}...")
        
        # Get user info from Bitbucket
        user_response = requests.get(
            "https://api.bitbucket.org/2.0/user",
            headers={
                "Authorization": f"Bearer {bitbucket_token}",
                "Accept": "application/json"
            }
        )
        user_response.raise_for_status()
        bitbucket_user = user_response.json()
        print(f"[Bitbucket OAuth] Got user: {bitbucket_user['username']}")
        
        # Check if user exists
        user = db.query(models.User).filter(
            models.User.bitbucket_id == str(bitbucket_user["uuid"])
        ).first()
        
        if not user:
            print(f"[Bitbucket OAuth] Creating new user: {bitbucket_user['username']}")
            # Create new user
            user = models.User(
                username=bitbucket_user["username"],
                bitbucket_id=str(bitbucket_user["uuid"]),
                bitbucket_username=bitbucket_user["username"],
                email=bitbucket_user.get("email"),
                auth_method="bitbucket",
                hashed_password=None  # No password for OAuth users
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            print(f"[Bitbucket OAuth] User created with ID: {user.id}")
        else:
            print(f"[Bitbucket OAuth] User exists with ID: {user.id}")
            # Update existing user's email if needed
            if bitbucket_user.get("email") and user.email != bitbucket_user.get("email"):
                user.email = bitbucket_user.get("email")
                db.commit()
        
        # Create JWT token
        access_token_expires = timedelta(minutes=config.JWT_EXPIRATION_MINUTES)
        access_token = jwt.encode(
            {
                "sub": str(user.id),
                "exp": datetime.now(timezone.utc) + access_token_expires
            },
            config.JWT_SECRET,
            algorithm="HS256"
        )
        
        print(f"[Bitbucket OAuth] Generated JWT token for user {user.id}")
        
        # If the request originated from the CLI, show the token explicitly for pasting back
        if state == "cli":
            from fastapi.responses import HTMLResponse
            html = f"""
            <html>
                <head>
                    <title>Zerokey CLI Login</title>
                    <style>
                        body {{ font-family: Arial, sans-serif; max-width: 720px; margin: 40px auto; padding: 0 16px; }}
                        pre {{ background: #0f172a; color: #e2e8f0; padding: 12px; border-radius: 8px; overflow-x: auto; }}
                        button {{ background: #0ea5e9; color: #0b1120; border: none; padding: 10px 14px; border-radius: 6px; cursor: pointer; font-size: 14px; }}
                        button:hover {{ background: #38bdf8; }}
                        .card {{ border: 1px solid #e2e8f0; border-radius: 10px; padding: 18px; }}
                    </style>
                </head>
                <body>
                    <div class="card">
                        <h2>CLI login successful</h2>
                        <p>Copy this JWT and paste it back into your terminal when prompted.</p>
                        <pre id="token">{access_token}</pre>
                        <button onclick="navigator.clipboard.writeText(document.getElementById('token').textContent)">Copy token</button>
                        <p style="margin-top:12px;">Keep this token secret. You can now close this tab or head to the dashboard.</p>
                        <p><a href="/static/dashboard.html">Open dashboard</a></p>
                    </div>
                </body>
            </html>
            """
            return HTMLResponse(html)

        # Default web flow: persist token in localStorage then send to dashboard
        from fastapi.responses import HTMLResponse
        html = f"""
        <html>
            <head>
                <script>
                    localStorage.setItem('access_token', '{access_token}');
                    window.location.href = '/static/dashboard.html';
                </script>
            </head>
            <body>
                <p>Redirecting to dashboard...</p>
            </body>
        </html>
        """
        return HTMLResponse(html)
        
    except requests.exceptions.RequestException as e:
        print(f"[Bitbucket OAuth] Request error: {str(e)}")
        error_msg = f"API+error:+{str(e)[:50]}"
        return RedirectResponse(url=f"/static/index.html?error={error_msg}")
    except Exception as e:
        print(f"[Bitbucket OAuth] Unexpected error: {str(e)}")
        error_msg = f"Error:+{str(e)[:50]}"
        return RedirectResponse(url=f"/static/index.html?error={error_msg}")


@router.delete("/account")
def delete_account(
    db: Session = Depends(database.get_db),
    current_user: models.User = Depends(dependencies.get_current_user),
):
    # Remove usage logs and API keys before deleting the user to satisfy FK constraints
    db.query(models.UsageLog).filter(models.UsageLog.user_id == current_user.id).delete()
    db.query(models.ApiKey).filter(models.ApiKey.user_id == current_user.id).delete()
    db.delete(current_user)
    db.commit()

    return {"message": "Account deleted"}
