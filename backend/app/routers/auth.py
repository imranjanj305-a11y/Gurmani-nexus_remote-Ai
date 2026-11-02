import pyotp
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import get_db
from ..deps import audit, current_user
from ..models import User
from ..schemas import LoginIn, MfaEnableIn, MfaSetupOut, RegisterIn, TokenOut
from ..security import create_access_token, hash_password, limiter, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenOut, status_code=201)
def register_first_admin(body: RegisterIn, db: Session = Depends(get_db)):
    """Bootstrap only: creates the master admin if no users exist yet."""
    if db.query(User).count() > 0:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Registration is closed")
    user = User(email=body.email.lower(), password_hash=hash_password(body.password), role="admin")
    db.add(user)
    db.commit()
    db.refresh(user)
    audit(db, "user.register_admin", user_id=user.id)
    return TokenOut(access_token=create_access_token(user.id, user.role))


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)):
    s = get_settings()
    key = f"login:{request.client.host if request.client else 'x'}:{body.email.lower()}"
    if not limiter.allow(key, s.login_max_attempts, s.login_window_seconds):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many attempts, try later")
    user = db.query(User).filter(User.email == body.email.lower()).first()
    if not user or not verify_password(body.password, user.password_hash):
        audit(db, "auth.login_failed", detail=body.email.lower())
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")
    if user.mfa_enabled:
        if not body.otp or not pyotp.TOTP(user.mfa_secret).verify(body.otp, valid_window=1):
            audit(db, "auth.mfa_failed", user_id=user.id)
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or missing OTP")
    audit(db, "auth.login", user_id=user.id)
    return TokenOut(access_token=create_access_token(user.id, user.role))


@router.post("/mfa/setup", response_model=MfaSetupOut)
def mfa_setup(user: User = Depends(current_user), db: Session = Depends(get_db)):
    secret = pyotp.random_base32()
    user.mfa_secret = secret
    user.mfa_enabled = False
    db.commit()
    uri = pyotp.TOTP(secret).provisioning_uri(name=user.email, issuer_name="Germani AI Nexus")
    return MfaSetupOut(secret=secret, otpauth_uri=uri)


@router.post("/mfa/enable")
def mfa_enable(body: MfaEnableIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if not user.mfa_secret or not pyotp.TOTP(user.mfa_secret).verify(body.otp, valid_window=1):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid OTP")
    user.mfa_enabled = True
    db.commit()
    audit(db, "auth.mfa_enabled", user_id=user.id)
    return {"mfa_enabled": True}
