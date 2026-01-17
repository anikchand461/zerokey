import os
from dotenv import load_dotenv

load_dotenv()

JWT_SECRET = os.getenv("JWT_SECRET")
JWT_EXPIRATION_MINUTES = int(os.getenv("JWT_EXPIRATION_MINUTES", 1440))  # default 1440 if missing

if not JWT_SECRET:
    raise ValueError("JWT_SECRET is missing in .env")

# Keep your other variables
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")
# Prefer Neon Postgres if provided, else fall back to DATABASE_URL, else local sqlite
DATABASE_URL = os.getenv("NEON_DATABASE_URL") or os.getenv("DATABASE_URL", "sqlite:///./vault.db")

# GitHub OAuth Configuration
GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")
GITHUB_REDIRECT_URI = os.getenv("GITHUB_REDIRECT_URI", "https://zerokey.onrender.com/auth/github/callback")

# GitLab OAuth Configuration
GITLAB_CLIENT_ID = os.getenv("GITLAB_CLIENT_ID")
GITLAB_CLIENT_SECRET = os.getenv("GITLAB_CLIENT_SECRET")
GITLAB_REDIRECT_URI = os.getenv("GITLAB_REDIRECT_URI", "https://zerokey.onrender.com/auth/gitlab/callback")

# Bitbucket OAuth Configuration
BITBUCKET_CLIENT_ID = os.getenv("BITBUCKET_CLIENT_ID")
BITBUCKET_CLIENT_SECRET = os.getenv("BITBUCKET_CLIENT_SECRET")
BITBUCKET_REDIRECT_URI = os.getenv("BITBUCKET_REDIRECT_URI", "https://zerokey.onrender.com/auth/bitbucket/callback")

