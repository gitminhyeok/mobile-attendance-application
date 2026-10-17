import os
import logging
from typing import Optional
from fastapi import Request, HTTPException
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from dotenv import load_dotenv
from database import get_db

load_dotenv()

logger = logging.getLogger(__name__)

# Secret key for signing cookies. No fallback: a predictable default would let
# anyone forge a session cookie for any uid (including admins).
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY environment variable must be set")
COOKIE_MAX_AGE = 60 * 60 * 24 * 7  # 7 days in seconds

_serializer = URLSafeTimedSerializer(SECRET_KEY)

ADMIN_UIDS = [str(uid).strip() for uid in os.getenv("ADMIN_UID", "").split(",") if uid.strip()]


def sign_uid(uid: str) -> str:
    """Sign a UID value for secure cookie storage."""
    return _serializer.dumps(uid)


def verify_uid(signed_value: str) -> Optional[str]:
    """Verify and extract UID from a signed cookie value. Returns None if invalid."""
    try:
        return _serializer.loads(signed_value, max_age=COOKIE_MAX_AGE)
    except SignatureExpired:
        logger.info("Session cookie expired")
        return None
    except BadSignature:
        logger.warning("Invalid session cookie signature detected")
        return None


def get_current_user_uid(request: Request) -> Optional[str]:
    """Extract and verify user UID from the signed session cookie."""
    signed_cookie = request.cookies.get("user_uid")
    if not signed_cookie:
        return None
    return verify_uid(signed_cookie)


def require_authenticated(request: Request) -> str:
    """FastAPI dependency: require a valid authenticated user. Raises 401 if not."""
    uid = get_current_user_uid(request)
    if not uid:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다.")
    return uid


def require_approved(request: Request) -> str:
    """FastAPI dependency: require an authenticated user whose membership is
    approved. Keeps pending/withdrawn members (with a still-valid cookie)
    away from member data and attendance marking."""
    uid = require_authenticated(request)
    db = get_db()
    if not db:
        raise HTTPException(status_code=500, detail="Database error")

    doc = db.collection("users").document(uid).get()
    if not doc.exists:
        raise HTTPException(status_code=403, detail="승인된 회원만 이용할 수 있습니다.")
    data = doc.to_dict() or {}
    # Same fallback semantics as the rest of the app: legacy docs without
    # is_auth fall back to status, defaulting to approved.
    is_auth = data.get("is_auth") or data.get("status", "approved")
    if is_auth != "approved":
        raise HTTPException(status_code=403, detail="승인된 회원만 이용할 수 있습니다.")
    return uid


def require_admin(request: Request) -> str:
    """FastAPI dependency: require an authenticated admin user. Raises 403 if not."""
    uid = require_authenticated(request)
    if uid not in ADMIN_UIDS:
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다.")
    return uid
