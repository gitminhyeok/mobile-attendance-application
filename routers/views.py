from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
import os
from database import get_db
from logic import check_ip, check_attendance_time, get_current_kst_time, get_client_ip
from datetime import datetime, timedelta
import calendar
from google.cloud.firestore_v1.base_query import FieldFilter

router = APIRouter()
templates = Jinja2Templates(directory="templates")

def get_ranking_data(db, target_date, valid_days_count, uid):
    current_month_prefix = target_date.strftime("%Y-%m")
    ranking_list = []
    
    if db:
        all_docs = db.collection("attendance").stream()
        user_stats = {}
        for doc in all_docs:
            data = doc.to_dict()
            if data.get('date', '').startswith(current_month_prefix):
                u_id = data['user_id']
                if u_id not in user_stats:
                    user_stats[u_id] = {'count': 0}
                user_stats[u_id]['count'] += 1

        sorted_stats = sorted(user_stats.items(), key=lambda x: x[1]['count'], reverse=True)
        
        current_rank = 0
        last_count = -1
        
        for u_id, stat in sorted_stats:
            count = stat['count']
            if count != last_count:
                current_rank += 1
            last_count = count
            
            u_doc = db.collection("users").document(u_id).get()
            u_data = u_doc.to_dict() if u_doc.exists else {}
            u_nick = u_data.get("nickname", "Unknown")
            u_profile = u_data.get("profile_image", "")
            
            rate = int((stat['count'] / valid_days_count) * 100)
            
            ranking_list.append({
                "rank": current_rank,
                "nickname": u_nick,
                "profile_image": u_profile,
                "count": count,
                "rate": rate,
                "is_me": (u_id == uid)
            })
    return ranking_list

@router.get("/api/ranking")
async def get_ranking_api(request: Request, year: int, month: int):
    uid = request.cookies.get("user_uid")
    db = get_db()
    
    try:
        target_date = datetime(year, month, 1)
    except ValueError:
        return JSONResponse(status_code=400, content={"message": "Invalid date"})

    # Valid Days Calculation
    now = get_current_kst_time()
    # Make now naive (remove timezone) for comparison with naive target_date
    now_naive = now.replace(tzinfo=None)
    
    valid_days_count = 0
    
    if target_date.strftime("%Y-%m") == now_naive.strftime("%Y-%m"):
        check_range = range(1, now_naive.day + 1)
        check_year, check_month = now_naive.year, now_naive.month
    elif target_date < now_naive.replace(day=1, hour=0, minute=0, second=0, microsecond=0):
        last_day = calendar.monthrange(target_date.year, target_date.month)[1]
        check_range = range(1, last_day + 1)
        check_year, check_month = target_date.year, target_date.month
    else:
        check_range = [] # Future
        check_year, check_month = target_date.year, target_date.month

    for day in check_range:
        d = datetime(check_year, check_month, day)
        if d.weekday() in [5, 6]: 
            valid_days_count += 1
    if valid_days_count == 0: valid_days_count = 1

    data = get_ranking_data(db, target_date, valid_days_count, uid)
    
    return JSONResponse({
        "ranking_list": data,
        "month_name": target_date.strftime("%B %Y"),
        "year": year,
        "month": month,
        "is_current_month": (target_date.strftime("%Y-%m") == now.strftime("%Y-%m"))
    })

def get_calendar_data(db, uid, target_date):
    """
    Generates a list of day objects for the requested month to render a heatmap.
    """
    year = target_date.year
    month = target_date.month
    last_day = calendar.monthrange(year, month)[1]
    
    # 1. Fetch Attendance for this month
    current_month_prefix = target_date.strftime("%Y-%m")
    attendance_map = {}
    
    if db:
        docs = (
            db.collection("attendance")
            .where(filter=FieldFilter("user_id", "==", uid))
            .where(filter=FieldFilter("date", ">=", f"{current_month_prefix}-01"))
            .where(filter=FieldFilter("date", "<=", f"{current_month_prefix}-{last_day}"))
            .stream()
        )
        for doc in docs:
            data = doc.to_dict()
            # Key: Day (int), Value: Status
            day_int = int(data['date'].split('-')[-1])
            attendance_map[day_int] = data['status'] # 'present' or 'late'

    # 2. Build Grid List
    calendar_grid = []
    
    # Add empty slots for days before the 1st of the month (to align weekdays)
    # weekday(): Mon=0, Sun=6. We want Sun to be last column? Or standard Calendar?
    # Let's use Standard: Sun(0) - Sat(6) or Mon(0) - Sun(6).
    # Let's stick to Mon(0) start for CSS Grid usually, or match Python weekday.
    # Python: Mon=0. Let's align 1st day.
    first_day_weekday = target_date.replace(day=1).weekday() # 0(Mon) to 6(Sun)
    
    # Fill leading empty spaces
    for _ in range(first_day_weekday):
        calendar_grid.append({"day": "", "status": "empty", "is_class": False, "is_today": False})
        
    now_date = datetime.now().date() # Local server time, or KST if preferred
    
    for day in range(1, last_day + 1):
        d = datetime(year, month, day)
        is_weekend = d.weekday() in [5, 6] # Sat, Sun
        status = attendance_map.get(day, "none")
        is_today = (d.date() == now_date)
        
        cell_status = "weekday" # Default
        if is_weekend:
            if status == "present":
                cell_status = "present"
            elif status == "late":
                cell_status = "late"
            else:
                cell_status = "absent" # Weekend but no record
        
        calendar_grid.append({
            "day": day,
            "status": cell_status, 
            "is_class": is_weekend,
            "is_today": is_today
        })
        
    return calendar_grid

@router.get("/api/record/calendar")
async def get_record_calendar_api(request: Request, year: int, month: int):
    uid = request.cookies.get("user_uid")
    if not uid:
        return JSONResponse(status_code=401, content={"message": "Unauthorized"})
    
    db = get_db()
    try:
        target_date = datetime(year, month, 1)
    except ValueError:
        return JSONResponse(status_code=400, content={"message": "Invalid date"})

    calendar_grid = get_calendar_data(db, uid, target_date)
    
    now = get_current_kst_time()
    # Check if current month to hide next button
    is_current = (target_date.strftime("%Y-%m") == now.strftime("%Y-%m"))
    
    return JSONResponse({
        "calendar_grid": calendar_grid,
        "month_name": target_date.strftime("%B %Y"),
        "year": year,
        "month": month,
        "is_current_month": is_current
    })

@router.get("/", response_class=HTMLResponse)
async def read_root(request: Request): # Removed query params from root
    # 1. Basic Setup
    # ... (Keep existing setup)
    uid = request.cookies.get("user_uid")
    nickname = None
    client_ip = get_client_ip(request)
    time_status, time_msg = check_attendance_time()
    is_ip_valid = check_ip(client_ip)
    already_attended = False
    
    db = get_db()
    
    # 2. Date Setup (Default to Now)
    now = get_current_kst_time()
    target_date = now 
    current_month_prefix = now.strftime("%Y-%m")
    today_str = now.strftime("%Y-%m-%d")
    
    # Calculate Valid Class Days
    valid_days_count = 0
    for day in range(1, now.day + 1):
        d = datetime(now.year, now.month, day)
        if d.weekday() in [5, 6]:
            valid_days_count += 1
    if valid_days_count == 0: valid_days_count = 1

    # 3. User Specific Data (Record)
    my_record = {
        "total_attendance": 0,
        "current_month_count": 0,
        "current_streak": 0,
        "total_points": 0,
        "attendance_rate": 0,
        "calendar": [] # Changed from history
    }
    
    if uid and db:
        # Get Nickname
        user_doc = db.collection("users").document(uid).get()
        if user_doc.exists:
            nickname = user_doc.to_dict().get("nickname")
            
        # Get Calendar Data for current month
        my_record["calendar"] = get_calendar_data(db, uid, now)

        # Get Total Stats (Separate query for total count)
        # Optimization: In real app, store totals on user doc. Here we count.
        # We need another query for ALL time stats if we want totals.
        # For simplicity in this edit, let's keep the logic or simplified query.
        
        # Calculate totals from ALL history stream
        docs = db.collection("attendance").where(filter=FieldFilter("user_id", "==", uid)).stream()
        
        for doc in docs:
            data = doc.to_dict()
            if data['date'] == today_str:
                already_attended = True
            
            my_record["total_attendance"] += 1
            my_record["total_points"] += data.get("point", 0)
            
            if data['date'].startswith(current_month_prefix):
                my_record["current_month_count"] += 1
        
        my_record["attendance_rate"] = int((my_record["current_month_count"] / valid_days_count) * 100)
        my_record["current_streak"] = my_record["current_month_count"] 

    # 4. Ranking Data (Initial Load using helper)
    ranking_list = get_ranking_data(db, target_date, valid_days_count, uid)

    context = {
        "request": request,
        "uid": uid,
        "nickname": nickname,
        "is_ip_valid": is_ip_valid,
        "time_status": time_status,
        "time_msg": time_msg,
        "already_attended": already_attended,
        "client_ip": client_ip,
        "my_record": my_record,
        "ranking_list": ranking_list,
        "valid_days_count": valid_days_count,
        "current_month_name": now.strftime("%B %Y"),
        "initial_year": now.year,
        "initial_month": now.month,
        "kakao_js_key": os.getenv("KAKAO_JS_KEY")
    }
    return templates.TemplateResponse("index.html", context)
    my_record = {
        "total_attendance": 0,
        "current_month_count": 0,
        "current_streak": 0,
        "total_points": 0,
        "attendance_rate": 0,
        "history": []
    }
    
    if uid and db:
        # Get Nickname from DB (Latest)
        user_doc = db.collection("users").document(uid).get()
        if user_doc.exists:
            user_data = user_doc.to_dict()
            nickname = user_data.get("nickname", "Unknown Warrior")
        else:
            nickname = "Unknown Warrior"
            
        # Get Attendance History
        docs = (
            db.collection("attendance")
            .where(filter=FieldFilter("user_id", "==", uid))
            .order_by("date", direction="DESCENDING")
            .stream()
        )
        
        for doc in docs:
            data = doc.to_dict()
            # Check today's attendance
            if data['date'] == today_str:
                already_attended = True
            
            # Record Stats
            my_record["history"].append(data)
            my_record["total_attendance"] += 1
            my_record["total_points"] += data.get("point", 0)
            
            if data['date'].startswith(current_month_prefix):
                my_record["current_month_count"] += 1
        
        # Calculate Rate
        my_record["attendance_rate"] = int((my_record["current_month_count"] / valid_days_count) * 100)
        # Simple Streak (placeholder)
        my_record["current_streak"] = my_record["current_month_count"] 

    # 4. Ranking Data
    ranking_list = []
    if db:
        # Fetch all attendance for this month (Optimization needed for scale)
        # Using a list to aggregate manually
        all_docs = db.collection("attendance").stream()
        
        user_stats = {}
        for doc in all_docs:
            data = doc.to_dict()
            if data.get('date', '').startswith(current_month_prefix):
                u_id = data['user_id']
                point = data.get('point', 0)
                
                if u_id not in user_stats:
                    user_stats[u_id] = {'count': 0, 'points': 0}
                user_stats[u_id]['count'] += 1
                user_stats[u_id]['points'] += point

        # Sort by Count (Attendance Count) instead of Points
        sorted_stats = sorted(user_stats.items(), key=lambda x: x[1]['count'], reverse=True)
        
        # Fetch Nicknames & Build List
        for rank, (u_id, stat) in enumerate(sorted_stats, 1):
            u_doc = db.collection("users").document(u_id).get()
            u_nick = u_doc.to_dict().get("nickname", "Unknown") if u_doc.exists else "Unknown"
            
            # Calculate Individual Rate
            rate = int((stat['count'] / valid_days_count) * 100)
            
            ranking_list.append({
                "rank": rank,
                "nickname": u_nick,
                "count": stat['count'],
                "points": stat['points'],
                "rate": rate,
                "is_me": (u_id == uid)
            })

    context = {
        "request": request,
        "uid": uid,
        "nickname": nickname,
        "is_ip_valid": is_ip_valid,
        "time_status": time_status,
        "time_msg": time_msg,
        "already_attended": already_attended,
        "client_ip": client_ip,
        # Record Data
        "my_record": my_record,
        "ranking_list": ranking_list,
        "valid_days_count": valid_days_count,
        "current_month_name": now.strftime("%B %Y"),
        "initial_year": now.year,
        "initial_month": now.month
    }
    return templates.TemplateResponse("index.html", context)

@router.get("/my", response_class=HTMLResponse)
async def read_my_attendance(request: Request):
    uid = request.cookies.get("user_uid")
    if not uid:
        return RedirectResponse("/login/kakao")

    db = get_db()
    nickname = "User"
    attendance_list = []
    
    total_attendance = 0
    total_points = 0
    current_month_count = 0
    current_streak = 0
    
    if db:
        # Get Nickname
        user_doc = db.collection("users").document(uid).get()
        if user_doc.exists:
            nickname = user_doc.to_dict().get("nickname", "User")

        # Fetch ALL attendance for this user to calculate detailed stats
        # Optimization: In a real app, aggregation queries or stored counters on the user doc are better.
        docs = (
            db.collection("attendance")
            .where(filter=FieldFilter("user_id", "==", uid))
            .order_by("date", direction="DESCENDING")
            .stream()
        )
            
        now = get_current_kst_time()
        current_month_prefix = now.strftime("%Y-%m")
        
        # Process docs
        # Since it's ordered descending (newest first), we can calculate streak easily.
        last_date = None
        streak_broken = False
        
        for doc in docs:
            data = doc.to_dict()
            date_str = data['date']
            status = data['status']
            point = data.get('point', 0)
            
            # Add to list (Full history or limited?) -> Let's show top 20 or all for now.
            attendance_list.append(data)
            
            # Total Stats
            total_attendance += 1
            total_points += point
            
            # Monthly Stats
            if date_str.startswith(current_month_prefix):
                current_month_count += 1
            
            # Streak Logic (Simplified: Consecutive class days attended)
            # This is tricky without knowing exactly which days were class days.
            # Simple approach: If the difference between this attendance and the previous one (in the loop) 
            # is <= 7 days (assuming weekly classes), we count it? 
            # Or just count total attendances as a "consistency score"?
            # Let's try a simple "consecutive attended records" approach if they are within reasonable gaps.
            # Actually, let's just use "current month count" as a proxy for "streak" for MVP simplicity, 
            # OR implement a real streak check:
            # - Sort dates. Check if every Saturday/Sunday between start and end has an attendance.
            # - Too complex for MVP.
            # - Alternative: "Consecutive Entries" without missing a week.
            
            if not streak_broken:
                # This logic is imperfect but serves as a placeholder
                current_streak += 1 
                # Ideally check gaps here.
                
    # Calculate valid weekend days in this month up to today
    valid_days_count = 0
    now = get_current_kst_time()
    for day in range(1, now.day + 1):
        d = datetime(now.year, now.month, day)
        if d.weekday() in [5, 6]: # Sat, Sun
            valid_days_count += 1
            
    attendance_rate = 0
    if valid_days_count > 0:
        attendance_rate = int((current_month_count / valid_days_count) * 100)

    context = {
        "request": request,
        "uid": uid,
        "nickname": nickname,
        "attendance_list": attendance_list, # Shows all history now
        "attendance_rate": attendance_rate,
        "valid_days_count": valid_days_count,
        "current_month": now.strftime("%B"), # Full month name
        "current_month_count": current_month_count,
        "total_attendance": total_attendance,
        "total_points": total_points,
        "current_streak": current_streak
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
