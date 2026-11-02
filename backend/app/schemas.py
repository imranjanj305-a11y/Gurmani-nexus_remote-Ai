from datetime import datetime
from pydantic import BaseModel, Field


class RegisterIn(BaseModel):
    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=10, max_length=128)


class LoginIn(BaseModel):
    email: str
    password: str
    otp: str | None = None


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MfaSetupOut(BaseModel):
    secret: str
    otpauth_uri: str


class MfaEnableIn(BaseModel):
    otp: str


class PairingCodeOut(BaseModel):
    code: str
    expires_at: datetime


class PairIn(BaseModel):
    code: str
    name: str = Field(min_length=1, max_length=120)
    platform: str = Field(min_length=2, max_length=30)
    model: str | None = None


class PairOut(BaseModel):
    device_id: int
    device_token: str


class HeartbeatIn(BaseModel):
    battery_percent: float | None = Field(default=None, ge=0, le=100)
    storage_total_mb: int | None = Field(default=None, ge=0)
    storage_free_mb: int | None = Field(default=None, ge=0)


class DeviceOut(BaseModel):
    id: int
    name: str
    platform: str
    model: str | None
    online: bool
    battery_percent: float | None
    storage_total_mb: int | None
    storage_free_mb: int | None
    last_seen: datetime | None


class AuditOut(BaseModel):
    id: int
    action: str
    device_id: int | None
    detail: str | None
    created_at: datetime
