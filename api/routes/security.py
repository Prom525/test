from typing import Callable, Dict, Any
from fastapi import Depends, HTTPException, Request

def get_claims(request: Request) -> Dict[str, Any]:
    """
    Verwacht dat jouw bestaande middleware/dependency claims al op request.state.claims zet.
    Pas dit aan naar jouw project.
    """
    claims = getattr(request.state, "claims", None)
    if not claims:
        raise HTTPException(status_code=401, detail="Missing auth claims")
    return claims

def has_role(claims: Dict[str, Any], role: str) -> bool:
    # Keycloak zet roles vaak in realm_access.roles
    realm_roles = (claims.get("realm_access") or {}).get("roles") or []
    if role in realm_roles:
        return True

    # of in resource_access[client].roles
    ra = claims.get("resource_access") or {}
    for _, v in ra.items():
        roles = v.get("roles") or []
        if role in roles:
            return True

    # soms in scope/permissions
    scopes = (claims.get("scope") or "").split()
    if role in scopes:
        return True

    return False

def require_role(role: str) -> Callable:
    def _dep(claims=Depends(get_claims)):
        if not has_role(claims, role):
            raise HTTPException(status_code=403, detail=f"Missing role: {role}")
        return True
    return _dep