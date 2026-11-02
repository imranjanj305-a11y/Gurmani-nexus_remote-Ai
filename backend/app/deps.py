from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session
import jwt

from .database import get_db
from .models import Device, User, AuditLog
from .security import decode_access_token, sha256


def audit(db: Session, action: str, user_id=None, device_id=None, detail=None) -> None:
    db.add(AuditLog(action=action, user_id=user_id, device_id=device_id, detail=detail))
    db.commit()


def _bearer(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")
    return authorization.split(" ", 1)[1].strip()


def current_user(authorization: str | None = Header(default=None), db: Session = Depends(get_db)) -> User:
    token = _bearer(authorization)
    try:
        payload = decode_access_token(token)
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")
    user = db.get(User, int(payload["sub"]))
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Unknown user")
    return user


def require_admin(user: User = Depends(current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin role required")
    return user


def current_device(authorization: str | None = Header(default=None), db: Session = Depends(get_db)) -> Device:
    token = _bearer(authorization)
    device = db.query(Device).filter(Device.token_hash == sha256(token)).first()
    if not device or device.revoked:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Device token invalid or revoked")
    return device
