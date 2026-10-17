import os
import logging
import calendar
from datetime import datetime
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from database import get_db
from logic import (
    check_ip, check_attendance_time, get_current_kst_time, get_client_ip,
    purge_expired_unnotified, count_valid_class_days, member_status,
    DROPOUT_DAYS, WARNING_DAYS, ACTIVE_DAYS,
)
from dependencies import get_current_user_uid, require_approved, ADMIN_UIDS
from google.cloud.firestore_v1.base_query import FieldFilter

logger = logging.getLogger(__name__)

router = APIRouter()
templates = Jinja2Templates(directory="templates")


def get_ranking_data(db, target_date, valid_days_count, uid):
    current_month_prefix = target_date.strftime("%Y-%m")
    ranking_list = []

    if not db:
        return ranking_list

    # Optimized: query by date range instead of full collection scan
    last_day = calendar.monthrange(target_date.year, target_date.month)[1]
    start_date = f"{current_month_prefix}-01"
    end_date = f"{current_month_prefix}-{last_day:02d}"

    docs = (
        db.collection("attendance")
        .where(filter=FieldFilter("date", ">=", start_date))
        .where(filter=FieldFilter("date", "<=", end_date))
        .stream()
    )

    counts = {}
    for doc in docs:
        data = doc.to_dict()
        # Only count if status is 'present' (exclude 'late')
        if data.get('status') == 'present':
            counts[data['user_id']] = counts.get(data['user_id'], 0) + 1

    if not counts:
        return ranking_list

    # Batch-fetch user docs (one round trip instead of one per member)
    refs = [db.collection("users").document(u_id) for u_id in counts]
    users = {snap.id: snap.to_dict() for snap in db.get_all(refs) if snap.exists}

    # Filter non-approved members BEFORE assigning ranks so the visible
    # numbering has no gaps
    visible = [
        (u_id, count) for u_id, count in counts.items()
        if u_id in users and member_status(users[u_id]) == "approved"
    ]
    visible.sort(key=lambda item: item[1], reverse=True)

    current_rank = 0
    last_count = None
    for u_id, count in visible:
        if count != last_count:
            current_rank += 1
        last_count = count

        u_data = users[u_id]
        ranking_list.append({
            "rank": current_rank,
            "nickname": u_data.get("nickname", "Unknown"),
            "profile_image": u_data.get("profile_image", ""),
            "count": count,
            "rate": int((count / valid_days_count) * 100),
            "is_me": (u_id == uid)
        })

    return ranking_list


@router.get("/api/ranking")
async def get_ranking_api(request: Request, year: int, month: int, uid: str = Depends(require_approved)):
    db = get_db()

    try:
        target_date = datetime(year, month, 1)
    except ValueError:
        return JSONResponse(status_code=400, content={"message": "Invalid date"})

    now = get_current_kst_time()
    valid_days_count = count_valid_class_days(year, month, now)

    data = get_ranking_data(db, target_date, valid_days_count, uid)

    return JSONResponse({
        "ranking_list": data,
        "month_name": target_date.strftime("%B %Y"),
        "year": year,
        "month": month,
        "is_current_month": (target_date.strftime("%Y-%m") == now.strftime("%Y-%m"))
    })


def compute_longest_weekly_streak(all_dates):
    """Longest run of consecutive ISO weeks with at least one attendance.
    `all_dates` must be ascending 'YYYY-MM-DD' strings.
    Returns (streak_weeks, last_date_of_best_run)."""
    if not all_dates:
        return 0, ""

    attended_weeks = sorted({datetime.strptime(d, "%Y-%m-%d").isocalendar()[:2] for d in all_dates})

    max_streak = 1
    current_streak = 1
    streak_end_date = all_dates[0]

    for i in range(1, len(attended_weeks)):
        prev_w = attended_weeks[i - 1]
        curr_w = attended_weeks[i]

        d1 = datetime.fromisocalendar(prev_w[0], prev_w[1], 1)
        d2 = datetime.fromisocalendar(curr_w[0], curr_w[1], 1)

        current_streak = current_streak + 1 if (d2 - d1).days == 7 else 1

        if current_streak >= max_streak:
            max_streak = current_streak
            week_dates = [d for d in all_dates if datetime.strptime(d, "%Y-%m-%d").isocalendar()[:2] == curr_w]
            if week_dates:
                streak_end_date = week_dates[-1]

    return max_streak, streak_end_date


def build_status_message(is_sick_leave, days_absent, unnotified_count, current_month_count):
    """Priority-ordered home screen status line. Returns (message, css_color)."""
    if is_sick_leave:
        return "병결 중이시네요, 회복 후 다시 만나요 💊", "text-blue-600"
    if days_absent == -1:
        return "첫 출석을 기다리고 있어요 🌱", "text-gray-500"
    if days_absent >= DROPOUT_DAYS or unnotified_count >= 2:
        reason = "미통보 불참 누적" if unnotified_count >= 2 else "장기 결석"
        return f"제적 대상입니다 🚨 ({reason})", "text-red-600"
    if days_absent >= WARNING_DAYS:
        return "벌써 2주째 참여하지 않았어요 ⚠️", "text-yellow-600"
    if days_absent < ACTIVE_DAYS:
        if current_month_count > 1:
            return "훌륭해요, 연속으로 참석 중이예요 🔥", "text-blue-600"
        return "이번 주에도 훈련에 참여했어요 👍", "text-black"
    return "어서오세요! 오늘도 힘내세요 💪", "text-gray-500"


def get_calendar_data(db, uid, target_date):
    year = target_date.year
    month = target_date.month
    last_day = calendar.monthrange(year, month)[1]

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
            day_int = int(data['date'].split('-')[-1])
            attendance_map[day_int] = data['status']

    calendar_grid = []
    first_day_weekday = target_date.replace(day=1).weekday()

    for _ in range(first_day_weekday):
        calendar_grid.append({"day": "", "status": "empty", "is_class": False, "is_today": False})

    # Fixed: use KST time instead of server local time
    now_date = get_current_kst_time().date()

    for day in range(1, last_day + 1):
        d = datetime(year, month, day)
        is_weekend = d.weekday() in [5, 6]
        status = attendance_map.get(day, "none")
        is_today = (d.date() == now_date)

        cell_status = "weekday"
        if is_weekend:
            if status == "present":
                cell_status = "present"
            elif status == "late":
                cell_status = "late"
            else:
                cell_status = "absent"

        calendar_grid.append({
            "day": day,
            "status": cell_status,
            "is_class": is_weekend,
            "is_today": is_today
        })

    return calendar_grid


@router.get("/api/record/calendar")
async def get_record_calendar_api(request: Request, year: int, month: int, uid: str = Depends(require_approved)):
    db = get_db()
    try:
        target_date = datetime(year, month, 1)
    except ValueError:
        return JSONResponse(status_code=400, content={"message": "Invalid date"})

    now = get_current_kst_time()
    valid_days_count = count_valid_class_days(year, month, now)

    calendar_grid = get_calendar_data(db, uid, target_date)

    current_month_count = 0
    for day in calendar_grid:
        if day.get('status') in ['present', 'late']:
            current_month_count += 1

    attendance_rate = int((current_month_count / valid_days_count) * 100)

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
async def read_root(request: Request):
    # 1. Basic Setup
    uid = get_current_user_uid(request)
    nickname = None
    client_ip = get_client_ip(request)
    time_status, time_msg = check_attendance_time()
    is_ip_valid = check_ip(client_ip)
    already_attended = False
    today_status = None

    db = get_db()

    # 2. Date Setup (Default to Now)
    now = get_current_kst_time()
    target_date = now
    current_month_prefix = now.strftime("%Y-%m")
    today_str = now.strftime("%Y-%m-%d")

    # Calculate Valid Class Days
    valid_days_count = count_valid_class_days(now.year, now.month, now)

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

    is_pending = False
    status_message = ""
    status_color = "text-gray-500"
    days_absent = -1
    unnotified_count = 0
    is_sick_leave = False

    # Check Admin
    is_admin_user = (str(uid).strip() in ADMIN_UIDS) if uid else False

    if uid and db:
        # Get User Doc & Check Status
        user_doc = db.collection("users").document(uid).get()
        if user_doc.exists:
            u_data = user_doc.to_dict()
            nickname = u_data.get("nickname")
            is_auth = member_status(u_data)

            # Additional Status Fields
            unnotified_date1, unnotified_date2 = purge_expired_unnotified(user_doc.reference, u_data, now.date())
            is_sick_leave = u_data.get("is_sick_leave", False)

            unnotified_count = 0
            if unnotified_date1: unnotified_count += 1
            if unnotified_date2: unnotified_count += 1

            # Any non-approved state (pending, withdrawn) gets the waiting
            # screen and no member data, even with a still-valid cookie
            if is_auth != "approved":
                is_pending = True

        # Only fetch data if NOT pending
        if not is_pending:
            my_record["calendar"] = get_calendar_data(db, uid, now)

            docs = db.collection("attendance").where(filter=FieldFilter("user_id", "==", uid)).order_by("date", direction="ASCENDING").stream()

            all_dates = []
            for doc in docs:
                data = doc.to_dict()
                date_str = data['date']
                all_dates.append(date_str)

                if date_str == today_str:
                    already_attended = True
                    today_status = data.get("status")

                my_record["total_attendance"] += 1
                my_record["total_points"] += data.get("point", 0)

                if date_str.startswith(current_month_prefix):
                    my_record["current_month_count"] += 1

            max_streak, streak_end_date = compute_longest_weekly_streak(all_dates)

            my_record["attendance_rate"] = int((my_record["current_month_count"] / valid_days_count) * 100)
            my_record["current_streak"] = max_streak
            if streak_end_date:
                try:
                    dt_obj = datetime.strptime(streak_end_date, "%Y-%m-%d")
                    my_record["streak_date"] = dt_obj.strftime("%y.%m.%d")
                except Exception:
                    my_record["streak_date"] = streak_end_date
            else:
                my_record["streak_date"] = ""

    # 4. Determine Status Message
    status_message = "첫 출석을 기다리고 있어요 🌱"
    status_color = "text-gray-500"

    if uid and db and not is_pending:
        last_attend_doc = (
            db.collection("attendance")
            .where(filter=FieldFilter("user_id", "==", uid))
            .order_by("date", direction="DESCENDING")
            .limit(1)
            .stream()
        )
        last_attend_list = list(last_attend_doc)
        days_absent = -1

        if last_attend_list:
            last_data = last_attend_list[0].to_dict()
            last_date_str = last_data['date']
            last_date = datetime.strptime(last_date_str, "%Y-%m-%d").date()
            days_absent = (now.date() - last_date).days

        status_message, status_color = build_status_message(
            is_sick_leave, days_absent, unnotified_count, my_record["current_month_count"])

    # 5. Ranking Data (Initial Load using helper)
    ranking_list = []
    if not is_pending:
        ranking_list = get_ranking_data(db, target_date, valid_days_count, uid)

    context = {
        "request": request,
        "uid": uid,
        "nickname": nickname,
        "is_pending": is_pending,
        "is_ip_valid": is_ip_valid,
        "time_status": time_status,
        "time_msg": time_msg,
        "already_attended": already_attended,
        "today_status": today_status,
        "client_ip": client_ip,
        "my_record": my_record,
        "ranking_list": ranking_list,
        "valid_days_count": valid_days_count,
        "current_month_name": now.strftime("%B %Y"),
        "current_month_num": now.month,
        "initial_year": now.year,
        "initial_month": now.month,
        "kakao_js_key": os.getenv("KAKAO_JS_KEY"),
        "status_message": status_message,
        "status_color": status_color,
        "is_admin_user": is_admin_user
    }
    return templates.TemplateResponse(request, "index.html", context)
