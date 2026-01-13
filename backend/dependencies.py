import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from jose import JWTError
from . import models, database, config

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")  # dummy – we use Auth0

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(database.get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        # Fetch JWKS (in production → cache this!)
        jwks_client = jwt.PyJWKClient(config.AUTH0_JWKS_URL)
        signing_key = jwks_client.get_signing_key_from_jwt(token)

        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=config.AUTH0_AUDIENCE,
            issuer=config.AUTH0_ISSUER,
        )
    except JWTError:
        raise credentials_exception

    sub = payload.get("sub")
    if sub is None:
        raise credentials_exception

    # Get or create user
    user = db.query(models.User).filter(models.User.auth0_sub == sub).first()
    if not user:
        email = payload.get("email")
        user = models.User(auth0_sub=sub, email=email)
        db.add(user)
        db.commit()
        db.refresh(user)

    return user
