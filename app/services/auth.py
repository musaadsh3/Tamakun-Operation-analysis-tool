import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session
from app.models import Admin
from app.config import settings

# Simple token store (in production, use Redis or DB-backed sessions)
_active_sessions: dict = {}


def hash_password(password: str) -> str:
    salt = os.urandom(32)
    key = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000)
    return salt.hex() + ':' + key.hex()


def verify_password(stored_hash: str, password: str) -> bool:
    try:
        salt_hex, key_hex = stored_hash.split(':')
        salt = bytes.fromhex(salt_hex)
        key = bytes.fromhex(key_hex)
        new_key = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000)
        return hmac.compare_digest(key, new_key)
    except Exception:
        return False


def authenticate_admin(db: Session, email: str, password: str) -> Optional[Admin]:
    admin = db.query(Admin).filter(Admin.email == email).first()
    if admin and verify_password(admin.password_hash, password):
        return admin
    return None


def create_session(admin: Admin) -> str:
    token = secrets.token_urlsafe(32)
    _active_sessions[token] = {
        "admin_id": admin.id,
        "email": admin.email,
        "name": admin.name,
        "expires": datetime.utcnow() + timedelta(hours=settings.SESSION_EXPIRE_HOURS),
    }
    return token


def get_session(token: str) -> Optional[dict]:
    session = _active_sessions.get(token)
    if not session:
        return None
    if datetime.utcnow() > session["expires"]:
        _active_sessions.pop(token, None)
        return None
    return session


def destroy_session(token: str):
    _active_sessions.pop(token, None)


def seed_admin(db: Session):
    """Create default admin if none exists."""
    existing = db.query(Admin).filter(Admin.email == settings.ADMIN_EMAIL).first()
    if not existing:
        admin = Admin(
            email=settings.ADMIN_EMAIL,
            name=settings.ADMIN_NAME,
            password_hash=hash_password(settings.ADMIN_DEFAULT_PASSWORD),
        )
        db.add(admin)
        db.commit()


def seed_brands(db: Session):
    """Create default brands if none exist."""
    from app.models import Brand
    defaults = [
        ("Best Shield", "بست شيلد", "bestshield"),
        ("Shabah", "شبة", "shabah"),
        ("Al Arabi", "أقمشة العربي", "alarabi"),
    ]
    for name, name_ar, key in defaults:
        existing = db.query(Brand).filter(Brand.processor_key == key).first()
        if not existing:
            db.add(Brand(name=name, name_ar=name_ar, processor_key=key))
    db.commit()
