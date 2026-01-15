import os
from dotenv import load_dotenv

load_dotenv()

JWT_SECRET = os.getenv("JWT_SECRET")
JWT_EXPIRATION_MINUTES = int(os.getenv("JWT_EXPIRATION_MINUTES", 1440))  # default 1440 if missing

if not JWT_SECRET:
    raise ValueError("JWT_SECRET is missing in .env")

# Keep your other variables
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./vault.db")

# GitHub OAuth Configuration
GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")
GITHUB_REDIRECT_URI = os.getenv("GITHUB_REDIRECT_URI", "http://localhost:8000/auth/github/callback")

