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


# ────────────────────────────────────────────────
# GitHub OAuth Routes
# ────────────────────────────────────────────────

@router.get("/github/login")
def github_login():
    """Redirect user to GitHub for authentication"""
    if not config.GITHUB_CLIENT_ID or not config.GITHUB_CLIENT_SECRET:
        raise HTTPException(400, detail="GitHub OAuth not configured. Set GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET in .env")
    
    github_auth_url = (
        f"https://github.com/login/oauth/authorize?"
        f"client_id={config.GITHUB_CLIENT_ID}&"
        f"redirect_uri={config.GITHUB_REDIRECT_URI}&"
        f"scope=user:email"
    )
    return RedirectResponse(url=github_auth_url)


@router.get("/github/callback")
def github_callback(
    code: str = None, 
    error: str = None, 
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
        
        # Redirect with token - using relative path with fragment to avoid query string issues
        # Store token temporarily in session and redirect
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
