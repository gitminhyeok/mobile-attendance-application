import logging
from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from database import get_db
from logic import check_ip, check_attendance_time, get_current_kst_time, get_client_ip
from dependencies import get_current_user_uid, require_authenticated
from firebase_admin import firestore
from google.cloud.firestore_v1.base_query import FieldFilter

logger = logging.getLogger(__name__)

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)


@router.post("/attendance")
@limiter.limit("10/minute")
async def mark_attendance(request: Request, uid: str = Depends(require_authenticated)):
    # 1. CSRF check: require custom header from JS fetch
    if request.headers.get("X-Requested-With") != "XMLHttpRequest":
        return JSONResponse(status_code=403, content={"message": "잘못된 요청입니다."})

    # 2. Check IP
    client_ip = get_client_ip(request)
    if not check_ip(client_ip):
        return JSONResponse(status_code=403, content={"message": "지정된 장소(와이파이)가 아닙니다."})

    # 3. Check Time
    status, message = check_attendance_time()
    if status == "closed":
        return JSONResponse(status_code=400, content={"message": message})

    # 4. Check Duplicate Attendance (Today)
    db = get_db()
    if not db:
        return JSONResponse(status_code=500, content={"message": "DB 연결 오류"})

    today_str = get_current_kst_time().strftime("%Y-%m-%d")

    docs = (
        db.collection("attendance")
        .where(filter=FieldFilter("user_id", "==", uid))
        .where(filter=FieldFilter("date", "==", today_str))
        .limit(1)
        .stream()
    )

    if any(docs):
        return JSONResponse(status_code=400, content={"message": "이미 오늘 출석을 완료했습니다."})

    # 5. Save Attendance
    status_text = "present" if status == "open" else "late"

    new_attendance = {
        "user_id": uid,
        "date": today_str,
        "timestamp": firestore.SERVER_TIMESTAMP,
        "status": status_text,
    }

    db.collection("attendance").add(new_attendance)

    return JSONResponse(status_code=200, content={"message": f"{ '출석' if status == 'open' else '지각' } 처리되었습니다!"})


@router.get("/attendance/status")
async def get_status(request: Request):
    uid = get_current_user_uid(request)
    client_ip = get_client_ip(request)

    is_ip_valid = check_ip(client_ip)
    time_status, time_msg = check_attendance_time()

    already_attended = False
    if uid:
        db = get_db()
        if db:
            today_str = get_current_kst_time().strftime("%Y-%m-%d")
            docs = (
                db.collection("attendance")
                .where(filter=FieldFilter("user_id", "==", uid))
                .where(filter=FieldFilter("date", "==", today_str))
                .limit(1)
                .stream()
            )
            if any(docs):
                already_attended = True

    return {
        "is_authenticated": bool(uid),
        "is_ip_valid": is_ip_valid,
        "time_status": time_status,
        "time_message": time_msg,
        "already_attended": already_attended,
        "client_ip": client_ip
    }
