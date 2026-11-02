from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import get_db
from ..deps import audit, current_device, require_admin
from ..models import AuditLog, Device, PairingCode, User, now
from ..schemas import (AuditOut, DeviceOut, HeartbeatIn, PairIn, PairOut, PairingCodeOut)
from ..security import limiter, new_device_token, new_pairing_code, sha256

router = APIRouter(tags=["devices"])


def _aware(dt):
    return dt if dt is None or dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _out(d: Device) -> DeviceOut:
    seen = _aware(d.last_seen)
    online = bool(seen and (datetime.now(timezone.utc) - seen).total_seconds() < get_settings().online_seconds)
    return DeviceOut(id=d.id, name=d.name, platform=d.platform, model=d.model, online=online and not d.revoked,
                     battery_percent=d.battery_percent, storage_total_mb=d.storage_total_mb,
                     storage_free_mb=d.storage_free_mb, last_seen=seen)


@router.post("/pairing/code", response_model=PairingCodeOut)
def create_pairing_code(user: User = Depends(require_admin), db: Session = Depends(get_db)):
    code = new_pairing_code()
    exp = now() + timedelta(minutes=get_settings().pairing_minutes)
    db.add(PairingCode(owner_id=user.id, code_hash=sha256(code), expires_at=exp))
    db.commit()
    audit(db, "pairing.code_created", user_id=user.id)
    return PairingCodeOut(code=code, expires_at=exp)


@router.post("/pairing/pair", response_model=PairOut, status_code=201)
def pair_device(body: PairIn, request: Request, db: Session = Depends(get_db)):
    if not limiter.allow(f"pair:{request.client.host if request.client else 'x'}", 10, 300):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many attempts")
    pc = db.query(PairingCode).filter(PairingCode.code_hash == sha256(body.code.strip().upper())).first()
    if not pc or pc.used or _aware(pc.expires_at) < datetime.now(timezone.utc):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid or expired pairing code")
    pc.used = True
    token = new_device_token()
    dev = Device(owner_id=pc.owner_id, name=body.name, platform=body.platform.lower(),
                 model=body.model, token_hash=sha256(token), last_seen=now())
    db.add(dev)
    db.commit()
    db.refresh(dev)
    audit(db, "device.paired", user_id=pc.owner_id, device_id=dev.id, detail=dev.platform)
    return PairOut(device_id=dev.id, device_token=token)


@router.post("/devices/me/heartbeat")
def heartbeat(body: HeartbeatIn, device: Device = Depends(current_device), db: Session = Depends(get_db)):
    device.battery_percent = body.battery_percent
    device.storage_total_mb = body.storage_total_mb
    device.storage_free_mb = body.storage_free_mb
    device.last_seen = now()
    db.commit()
    return {"ok": True}


@router.get("/devices", response_model=list[DeviceOut])
def list_devices(user: User = Depends(require_admin), db: Session = Depends(get_db)):
    devs = db.query(Device).filter(Device.owner_id == user.id, Device.revoked == False).all()  # noqa: E712
    return [_out(d) for d in devs]


@router.delete("/devices/{device_id}")
def revoke_device(device_id: int, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    dev = db.get(Device, device_id)
    if not dev or dev.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Device not found")
    dev.revoked = True
    db.commit()
    audit(db, "device.revoked", user_id=user.id, device_id=dev.id)
    return {"revoked": True}


@router.get("/audit", response_model=list[AuditOut])
def audit_logs(user: User = Depends(require_admin), db: Session = Depends(get_db)):
    rows = db.query(AuditLog).order_by(AuditLog.id.desc()).limit(200).all()
    return [AuditOut(id=r.id, action=r.action, device_id=r.device_id, detail=r.detail, created_at=r.created_at) for r in rows]
