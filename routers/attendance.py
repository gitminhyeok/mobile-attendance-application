from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import JSONResponse
from database import get_db
from logic import check_ip, check_attendance_time, get_current_kst_time
from firebase_admin import firestore
import logging

router = APIRouter()

@router.post("/attendance")
async def mark_attendance(request: Request):
    # 1. Get User UID from Cookie
    uid = request.cookies.get("user_uid")
    if not uid:
        return JSONResponse(status_code=401, content={"message": "로그인이 필요합니다."})

    # 2. Check IP
    client_ip = request.client.host
    if not check_ip(client_ip):
         # Note: In production behind proxy, use X-Forwarded-For
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
    
    # Query: attendance where user_id == uid and date == today
    docs = (
        db.collection("attendance")
        .where("user_id", "==", uid)
        .where("date", "==", today_str)
        .limit(1)
        .stream()
    )
    
    if any(docs):
        return JSONResponse(status_code=400, content={"message": "이미 오늘 출석을 완료했습니다."})

    # 5. Save Attendance
    point = 10 if status == "open" else 5
    status_text = "present" if status == "open" else "late"
    
    new_attendance = {
        "user_id": uid,
        "date": today_str,
        "timestamp": firestore.SERVER_TIMESTAMP,
        "status": status_text,
        "point": point
    }
    
    db.collection("attendance").add(new_attendance)
    
    return JSONResponse(status_code=200, content={"message": f"{ '출석' if status == 'open' else '지각' } 처리되었습니다! (+{point}점)"})

@router.get("/attendance/status")
async def get_status(request: Request):
    """
    Returns current user's status for the main button
    """
    uid = request.cookies.get("user_uid")
    client_ip = request.client.host
    
    # Basic Checks
    is_ip_valid = check_ip(client_ip)
    time_status, time_msg = check_attendance_time()
    
    already_attended = False
    if uid:
        db = get_db()
        if db:
            today_str = get_current_kst_time().strftime("%Y-%m-%d")
            docs = (
                db.collection("attendance")
                .where("user_id", "==", uid)
                .where("date", "==", today_str)
                .limit(1)
                .stream()
            )
            if any(docs):
                already_attended = True

    return {
        "is_authenticated": bool(uid),
        "is_ip_valid": is_ip_valid,
        "time_status": time_status, # open, late, closed
        "time_message": time_msg,
        "already_attended": already_attended,
        "client_ip": client_ip
    }
