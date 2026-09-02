
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from .config import settings
import requests

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Load JWKS
jwks = requests.get(settings.KEYCLOAK_JWKS_URL).json()

def get_signing_key(kid):
    for key in jwks['keys']:
        if key['kid'] == kid:
            return key
    raise HTTPException(status_code=401, detail="Invalid token: unknown kid")

def verify_token(token: str = Depends(oauth2_scheme)):
    try:
        header = jwt.get_unverified_header(token)
        signing_key = get_signing_key(header['kid'])
        payload = jwt.decode(
            token,
            signing_key,
            algorithms=header['alg'],
            audience=settings.KEYCLOAK_AUDIENCE,
            issuer=settings.KEYCLOAK_ISSUER
        )
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
