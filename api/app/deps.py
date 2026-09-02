# C:\ai-platform\api\app\deps.py
import os
from typing import Callable, Dict, Any, Optional

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

# ----------------------------
# DB dependency
# ----------------------------
_engine: Optional[Engine] = None

def get_engine() -> Engine:
    """
    SQLAlchemy Engine singleton op DATABASE_URL (uit docker-compose environment).
    """
    global _engine
    if _engine is None:
        db_url = os.environ.get("DATABASE_URL")
        if not db_url:
            raise RuntimeError("DATABASE_URL is not set")
        _engine = create_engine(db_url, pool_pre_ping=True)
    return _engine


# ----------------------------
# Auth / Roles (nu stub)
# ----------------------------
def require_auth():
    # TODO: valideren met Keycloak via JWKS
    return True

def get_claims(request: Request) -> Dict[str, Any]:
    """
    In de toekomst: claims uit JWT.
    Voor nu: probeer request.state.claims; anders empty dict.
    """
    return getattr(request.state, "claims", {}) or {}

def has_role(claims: Dict[str, Any], role: str) -> bool:
    # Keycloak patterns:
    realm_roles = (claims.get("realm_access") or {}).get("roles") or []
    if role in realm_roles:
        return True

    ra = claims.get("resource_access") or {}
    for _, v in ra.items():
        roles = v.get("roles") or []
        if role in roles:
            return True

    scopes = (claims.get("scope") or "").split()
    if role in scopes:
        return True

    return False

def require_role(role: str) -> Callable:
    """
    Dependency die role afdwingt.
    LET OP: zolang require_auth() nog stub is, kun je hier tijdelijk alles toelaten.
    """
    def _dep(
        _auth=Depends(require_auth),
        claims=Depends(get_claims),
    ):
        # Tijdelijke modus voor lokale test:
        # - Als er nog geen claims zijn, laat toe.
        # - Zodra je JWT-validatie aanzet, wordt dit echt enforced.
        if claims and not has_role(claims, role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing role: {role}",
            )
        return True
    return _dep


