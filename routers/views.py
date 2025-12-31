from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from database import get_db
from logic import check_ip, check_attendance_time, get_current_kst_time
from datetime import datetime

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    # Get User Info
    uid = request.cookies.get("user_uid")
    nickname = None
    
    # Check Status
    client_ip = request.client.host
    time_status, time_msg = check_attendance_time()
    is_ip_valid = check_ip(client_ip)
    
    already_attended = False
    
    if uid:
        db = get_db()
        if db:
            # Get Nickname (optional, could be cached)
            user_doc = db.collection("users").document(uid).get()
            if user_doc.exists:
                nickname = user_doc.to_dict().get("nickname")
            
            # Check if attended today
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

    context = {
        "request": request,
        "uid": uid,
        "nickname": nickname,
        "is_ip_valid": is_ip_valid,
        "time_status": time_status, # open, late, closed
        "time_msg": time_msg,
        "already_attended": already_attended,
        "client_ip": client_ip
    }
    return templates.TemplateResponse("index.html", context)

@router.get("/my", response_class=HTMLResponse)
async def read_my_attendance(request: Request):
    uid = request.cookies.get("user_uid")
    if not uid:
        return RedirectResponse("/login/kakao")

    db = get_db()
    nickname = "사용자"
    attendance_list = []
    stats = {"total": 0, "present": 0, "late": 0, "rate": 0}
    
    if db:
        # Get Nickname
        user_doc = db.collection("users").document(uid).get()
        if user_doc.exists:
            nickname = user_doc.to_dict().get("nickname")

        # Get Attendance for current month
        # Note: Firestore filtering by string date "YYYY-MM" requires range query or storing month field.
        # For simplicity, we'll fetch all and filter in python or fetch year-month range.
        # Let's fetch all for this user for now (assuming not huge data).
        
        now = get_current_kst_time()
        current_month_prefix = now.strftime("%Y-%m")
        
        docs = (
            db.collection("attendance")
            .where("user_id", "==", uid)
            .order_by("date", direction="DESCENDING")
            .stream()
        )
            
        for doc in docs:
            data = doc.to_dict()
            if data['date'].startswith(current_month_prefix):
                attendance_list.append(data)
                stats['total'] += 1
                if data['status'] == 'present':
                    stats['present'] += 1
                elif data['status'] == 'late':
                    stats['late'] += 1
        
        if stats['total'] > 0:
            stats['rate'] = int((stats['present'] + stats['late']) / stats['total'] * 100) # Simple calculation
            # Wait, rate usually means 'attendance count / total possible days'.
            # But we don't know total possible days easily.
            # PRD says "Attendance Percentage". Let's just show (Attended / Total Class Days so far)?
            # Or just "Attendance Rate" as (Present + Late) / Total Recorded? -> That's 100%.
            # Maybe it means (Present count / Total Attended count)?
            # Let's interpret as: "attendance rate" = (days attended) / (days elapsed in month that were class days).
            # This is hard without a schedule.
            # Alternative: Just show "XX%" where XX is number of attendances? No.
            # Let's just show "Attendance Count" and maybe "Late Count".
            # Re-reading PRD: "This month's attendance percentage".
            # I will implement it as: (Attended Days) / (Saturdays + Sundays passed so far in this month).
            
            # Calculate total weekend days passed in this month
            pass

    # Calculate valid weekend days in this month up to today
    valid_days_count = 0
    now = get_current_kst_time()
    for day in range(1, now.day + 1):
        d = datetime(now.year, now.month, day)
        if d.weekday() in [5, 6]: # Sat, Sun
            valid_days_count += 1
            
    attendance_rate = 0
    if valid_days_count > 0:
        attendance_rate = int((len(attendance_list) / valid_days_count) * 100)

    context = {
        "request": request,
        "uid": uid,
        "nickname": nickname,
        "attendance_list": attendance_list,
        "attendance_rate": attendance_rate,
        "valid_days_count": valid_days_count,
        "current_month": now.month
    }
    return templates.TemplateResponse("my_attendance.html", context)

@router.get("/ranking", response_class=HTMLResponse)
async def read_ranking(request: Request):
    db = get_db()
    ranking_list = []
    
    if db:
        # Get all attendance for current month
        # Optimization: Maintain a separate 'monthly_stats' collection or increment counters on user.
        # For MVP: Scan attendance.
        
        now = get_current_kst_time()
        current_month_prefix = now.strftime("%Y-%m")
        
        # Get all attendance for this month
        docs = db.collection("attendance").stream() # Ideally filter by date >= start_of_month
        
        user_stats = {}
        
        for doc in docs:
            data = doc.to_dict()
            if data.get('date', '').startswith(current_month_prefix):
                uid = data['user_id']
                point = data.get('point', 0)
                
                if uid not in user_stats:
                    user_stats[uid] = {'count': 0, 'points': 0}
                
                user_stats[uid]['count'] += 1
                user_stats[uid]['points'] += point

        # Convert to list and sort
        sorted_stats = sorted(user_stats.items(), key=lambda x: x[1]['points'], reverse=True)
        
        # Fetch nicknames for top users (e.g., top 50)
        for rank, (uid, stat) in enumerate(sorted_stats, 1):
            user_doc = db.collection("users").document(uid).get()
            nickname = "Unknown"
            if user_doc.exists:
                nickname = user_doc.to_dict().get("nickname", "Unknown")
            
            ranking_list.append({
                "rank": rank,
                "nickname": nickname,
                "count": stat['count'],
                "points": stat['points']
            })

    context = {
        "request": request,
        "ranking_list": ranking_list,
        "current_month": get_current_kst_time().month
    }
    return templates.TemplateResponse("ranking.html", context)
