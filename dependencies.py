import os
import logging
from typing import Optional
from fastapi import Request, HTTPException
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Secret key for signing cookies - MUST be set in production
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-in-production")
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


def require_admin(request: Request) -> str:
    """FastAPI dependency: require an authenticated admin user. Raises 403 if not."""
    uid = require_authenticated(request)
    if uid not in ADMIN_UIDS:
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다.")
    return uid
