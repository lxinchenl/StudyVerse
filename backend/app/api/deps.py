from fastapi import Header, HTTPException

from app.core.dependencies import get_auth_service


def require_user_id(x_user_id: str | None = Header(default=None, alias="X-User-Id")) -> str:
    if not x_user_id:
        raise HTTPException(status_code=401, detail="Missing X-User-Id header")
    user = get_auth_service().get_user(x_user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return x_user_id
