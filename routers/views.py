from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from database import get_db
from logic import check_ip, check_attendance_time, get_current_kst_time, get_client_ip
from datetime import datetime, timedelta, time
import calendar
import os
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
            # Only count if status is 'present' (exclude 'late')
            if data.get('date', '').startswith(current_month_prefix) and data.get('status') == 'present':
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
            # If checking today, verify start time
            if d.date() == now.date():
                if d.weekday() == 5 and now.time() < time(12, 45): continue
                if d.weekday() == 6 and now.time() < time(15, 45): continue
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

    # 1. Valid Days Calculation for the target month
    valid_days_count = 0
    last_day = calendar.monthrange(year, month)[1]
    now = get_current_kst_time()
    
    # Logic to count valid days (Sat/Sun) up to today if current month, or all month if past
    check_range = range(1, last_day + 1)
    
    # If future month, valid days is 0 (or estimation? let's say 0 for now or estimate based on full month)
    # Actually, for rate calculation, we usually compare against "days passed so far" or "total class days in month".
    # Let's use "Total class days in month" for past months, and "Days passed" for current.
    
    if target_date.strftime("%Y-%m") == now.strftime("%Y-%m"):
        # Current month: count up to today
        check_range = range(1, now.day + 1)
    elif target_date > now:
        check_range = [] # Future
    else:
        # Past month: full month
        check_range = range(1, last_day + 1)

    for day in check_range:
        d = datetime(year, month, day)
        if d.weekday() in [5, 6]: # Sat, Sun
             # For current day check time? Simplified: just count day if it's passed or today
             valid_days_count += 1
             
    if valid_days_count == 0: valid_days_count = 1 # Avoid division by zero

    # 2. Get Calendar & Count
    calendar_grid = get_calendar_data(db, uid, target_date)
    
    # Count present from the grid data (since get_calendar_data already fetches it)
    current_month_count = 0
    for day in calendar_grid:
        if day.get('status') == 'present':
            current_month_count += 1
            
    attendance_rate = int((current_month_count / valid_days_count) * 100)
    
    # Check if current month to hide next button
    is_current = (target_date.strftime("%Y-%m") == now.strftime("%Y-%m"))
    
    return JSONResponse({
        "calendar_grid": calendar_grid,
        "month_name": target_date.strftime("%B %Y"),
        "year": year,
        "month": month,
        "month_num": month,
        "short_year": str(year)[-2:],
        "is_current_month": is_current,
        "attendance_count": current_month_count,
        "attendance_rate": attendance_rate,
        "valid_days_count": valid_days_count
    })

@router.get("/", response_class=HTMLResponse)
async def read_root(request: Request): # Removed query params from root
    # 1. Basic Setup
    uid = request.cookies.get("user_uid")
    nickname = None
    client_ip = get_client_ip(request)
    time_status, time_msg = check_attendance_time()
    is_ip_valid = check_ip(client_ip)
    already_attended = False
    today_status = None # To store 'present' or 'late'
    
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
            # If checking today, verify start time
            if d.date() == now.date():
                if d.weekday() == 5 and now.time() < time(12, 45): continue
                if d.weekday() == 6 and now.time() < time(15, 45): continue
            valid_days_count += 1
    if valid_days_count == 0: valid_days_count = 1

    # 3. User Specific Data (Record)
    my_record = {
        "total_attendance": 0,
        "current_month_count": 0,
        "current_streak": 0,
        "total_points": 0,
        "attendance_rate": 0,
        "calendar": [],
        "streak_date": ""
    }
    
    is_pending = False # New flag
    
    if uid and db:
        # Get User Doc & Check Status
        user_doc = db.collection("users").document(uid).get()
        if user_doc.exists:
            u_data = user_doc.to_dict()
            nickname = u_data.get("nickname")
            # Check is_auth first, then fallback to status, then default to approved
            is_auth = u_data.get("is_auth") or u_data.get("status", "approved")
            
            # Additional Status Fields
            unnotified_date1 = u_data.get("unnotified_date1", "")
            unnotified_date2 = u_data.get("unnotified_date2", "")
            is_sick_leave = u_data.get("is_sick_leave", False)
            
            unnotified_count = 0
            if unnotified_date1: unnotified_count += 1
            if unnotified_date2: unnotified_count += 1
            
            if is_auth == "pending":
                is_pending = True
            
        # Only fetch data if NOT pending
        if not is_pending:
            # Get Calendar Data for current month
            my_record["calendar"] = get_calendar_data(db, uid, now)

            # Get Total Stats (Separate query for total count)
            # Optimization: In real app, store totals on user doc. Here we count.
            
            # Calculate totals from ALL history stream
            docs = db.collection("attendance").where(filter=FieldFilter("user_id", "==", uid)).order_by("date", direction="ASCENDING").stream()
            
            all_dates = []
            for doc in docs:
                data = doc.to_dict()
                date_str = data['date']
                all_dates.append(date_str)
                
                if date_str == today_str:
                    already_attended = True
                    today_status = data.get("status") # Capture status (present/late)
                
                my_record["total_attendance"] += 1
                my_record["total_points"] += data.get("point", 0)
                
                if date_str.startswith(current_month_prefix):
                    my_record["current_month_count"] += 1
            
            # Calculate Longest Weekly Streak
            max_streak = 0
            current_streak = 0
            streak_end_date = ""
            
            if all_dates:
                # Get unique ISO weeks: set of (year, week)
                attended_weeks = sorted(list(set([datetime.strptime(d, "%Y-%m-%d").isocalendar()[:2] for d in all_dates])))
                
                if attended_weeks:
                    current_streak = 1
                    max_streak = 1
                    streak_end_date = all_dates[0] # Initial
                    
                    for i in range(1, len(attended_weeks)):
                        prev_w = attended_weeks[i-1]
                        curr_w = attended_weeks[i]
                        
                        # Check if consecutive week
                        d1 = datetime.fromisocalendar(prev_w[0], prev_w[1], 1)
                        d2 = datetime.fromisocalendar(curr_w[0], curr_w[1], 1)
                        
                        if (d2 - d1).days == 7:
                            current_streak += 1
                        else:
                            current_streak = 1
                        
                        if current_streak >= max_streak:
                            max_streak = current_streak
                            week_dates = [d for d in all_dates if datetime.strptime(d, "%Y-%m-%d").isocalendar()[:2] == curr_w]
                            if week_dates:
                                streak_end_date = week_dates[-1]

            my_record["attendance_rate"] = int((my_record["current_month_count"] / valid_days_count) * 100)
            my_record["current_streak"] = max_streak
            # Format date to YY.MM.DD
            if streak_end_date:
                try:
                    dt_obj = datetime.strptime(streak_end_date, "%Y-%m-%d")
                    my_record["streak_date"] = dt_obj.strftime("%y.%m.%d")
                except:
                    my_record["streak_date"] = streak_end_date
            else:
                my_record["streak_date"] = ""

    # 4. Determine Status Message
    status_message = "첫 출석을 기다리고 있어요 🌱"
    status_color = "text-gray-500"
    
    if uid and db and not is_pending:
        # Get last attendance for message logic
        last_attend_doc = (
            db.collection("attendance")
            .where(filter=FieldFilter("user_id", "==", uid))
            .order_by("date", direction="DESCENDING")
            .limit(1)
            .stream()
        )
        last_attend_list = list(last_attend_doc)
        days_absent = -1 # Default: No record
        
        if last_attend_list:
            last_data = last_attend_list[0].to_dict()
            last_date_str = last_data['date']
            last_date = datetime.strptime(last_date_str, "%Y-%m-%d").date()
            days_absent = (now.date() - last_date).days
        
        # Status Priority Logic
        if is_sick_leave:
            status_message = "병결 중이시네요, 회복 후 다시 만나요 💊"
            status_color = "text-blue-600"
        elif days_absent == -1:
            status_message = "첫 출석을 기다리고 있어요 🌱"
            status_color = "text-gray-500"
        elif days_absent >= 21 or unnotified_count >= 2:
            reason = "미통보 불참 누적" if unnotified_count >= 2 else "장기 결석"
            status_message = f"제적 대상입니다 🚨 ({reason})"
            status_color = "text-red-600"
        elif days_absent >= 14:
            status_message = "벌써 2주째 참여하지 않았어요 ⚠️"
            status_color = "text-yellow-600"
        elif days_absent < 7:
            if my_record["current_month_count"] > 1:
                status_message = "훌륭해요, 연속으로 참석 중이예요 🔥"
                status_color = "text-blue-600"
            else:
                status_message = "이번 주에도 훈련에 참여했어요 👍"
                status_color = "text-black"
        else:
            status_message = "어서오세요! 오늘도 힘내세요 💪"
            status_color = "text-gray-500"

    # 5. Ranking Data (Initial Load using helper)
    ranking_list = []
    if not is_pending:
        ranking_list = get_ranking_data(db, target_date, valid_days_count, uid)

    context = {
        "request": request,
        "uid": uid,
        "nickname": nickname,
        "is_pending": is_pending, # Added
        "is_ip_valid": is_ip_valid,
        "time_status": time_status,
        "time_msg": time_msg,
        "already_attended": already_attended,
        "client_ip": client_ip,
        "my_record": my_record,
        "ranking_list": ranking_list,
        "valid_days_count": valid_days_count,
        "current_month_name": now.strftime("%B %Y"),
        "current_month_num": now.month, # Added month number
        "initial_year": now.year,
        "initial_month": now.month,
        "kakao_js_key": os.getenv("KAKAO_JS_KEY"),
        "status_message": status_message,
        "status_color": status_color
    }
    return templates.TemplateResponse("index.html", context)