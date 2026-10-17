import os
import calendar
from datetime import datetime, time
import pytz
from dotenv import load_dotenv

load_dotenv()

# Constants
KST = pytz.timezone('Asia/Seoul')
ALLOWED_IP = os.getenv("ALLOWED_IP", "127.0.0.1")

# Absence thresholds (days since last attendance)
# 3 weeks + 2 day buffer for weekday gap between training sessions
DROPOUT_DAYS = 23   # 21 + 2: eligible for removal
WARNING_DAYS = 16   # 14 + 2: warning threshold
ACTIVE_DAYS = 9     #  7 + 2: considered actively attending

# Unnotified absence records expire after this many months
UNNOTIFIED_EXPIRY_MONTHS = 3

# Max length of the admin memo on a user
MEMO_MAX_LENGTH = 50

# Weekend class schedule (KST): weekday -> (attend_start, late_start, close)
# present: attend_start <= t < late_start, late: late_start <= t < close
CLASS_SCHEDULE = {
    5: (time(12, 45), time(13, 11), time(14, 0)),   # Saturday, 13:00 class
    6: (time(15, 45), time(16, 11), time(17, 0)),   # Sunday, 16:00 class
}


def member_status(user_data) -> str:
    """Membership state with the app-wide fallback: legacy docs without
    is_auth fall back to status, defaulting to approved."""
    data = user_data or {}
    return data.get("is_auth") or data.get("status", "approved")


def parse_unnotified_date(date_str: str):
    """Parse an unnotified date stored as 'YY-MM-DD' (or 'YYYY-MM-DD'). Returns None if invalid."""
    for fmt in ("%y-%m-%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_str.strip(), fmt).date()
        except (ValueError, AttributeError):
            continue
    return None


def subtract_months(d, months: int):
    """Return the same day `months` months earlier, clamped to the end of the month."""
    month_index = d.year * 12 + (d.month - 1) - months
    year, month = divmod(month_index, 12)
    month += 1
    last_day = calendar.monthrange(year, month)[1]
    return d.replace(year=year, month=month, day=min(d.day, last_day))


def purge_expired_unnotified(user_ref, user_data: dict, today) -> tuple:
    """
    Drop unnotified dates older than UNNOTIFIED_EXPIRY_MONTHS and write the change back.
    Remaining dates are compacted into unnotified_date1 first.
    Returns the (unnotified_date1, unnotified_date2) that are still valid.
    """
    original = [user_data.get("unnotified_date1", "") or "", user_data.get("unnotified_date2", "") or ""]
    cutoff = subtract_months(today, UNNOTIFIED_EXPIRY_MONTHS)

    kept = []
    for date_str in original:
        if not date_str:
            continue
        parsed = parse_unnotified_date(date_str)
        # Keep unparseable values so an admin can fix them by hand
        if parsed is None or parsed >= cutoff:
            kept.append(date_str)

    kept += [""] * (2 - len(kept))

    if kept != original:
        user_ref.update({"unnotified_date1": kept[0], "unnotified_date2": kept[1]})

    return kept[0], kept[1]

def get_client_ip(request):
    """
    Extracts the real client IP address, handling proxies (X-Forwarded-For).
    """
    x_forwarded_for = request.headers.get("x-forwarded-for")
    if x_forwarded_for:
        # X-Forwarded-For: <client>, <proxy1>, <proxy2>
        ip = x_forwarded_for.split(",")[0].strip()
        return ip
    return request.client.host

def check_ip(client_ip: str) -> bool:
    """
    Check if the client IP matches the allowed gym IP.
    """
    # For local development, allow localhost
    if client_ip == "127.0.0.1" or client_ip == "::1":
        return True
    
    # Check against allowed IP (supports multiple IPs comma separated if needed)
    allowed_ips = [ip.strip() for ip in ALLOWED_IP.split(",")]
    return client_ip in allowed_ips

def get_current_kst_time():
    return datetime.now(KST)

def check_attendance_time():
    """
    Check if the current time is within the attendance window.
    Returns:
        status (str): "open", "late", "closed"
        message (str): Description
    """
    now = get_current_kst_time()
    schedule = CLASS_SCHEDULE.get(now.weekday())  # Monday=0, Sunday=6

    if not schedule:
        return "closed", "오늘은 훈련일이 아닙니다."

    attend_start, late_start, close = schedule
    current_time = now.time()

    if attend_start <= current_time < late_start:
        return "open", "출석 가능"
    if late_start <= current_time < close:
        return "late", "지각"
    return "closed", "출석 시간이 아닙니다."


def count_valid_class_days(year: int, month: int, now=None) -> int:
    """Number of weekend class days of the month that count toward the
    attendance-rate denominator, as of `now` (KST).

    Past months count every weekend day, future months none, and the current
    month counts up to today -- excluding today's class while it has not
    started yet. Returns at least 1 so callers can divide safely.
    """
    now = now or get_current_kst_time()
    target = (year, month)
    current = (now.year, now.month)

    if target == current:
        days = range(1, now.day + 1)
    elif target < current:
        days = range(1, calendar.monthrange(year, month)[1] + 1)
    else:
        days = range(0)

    count = 0
    for day in days:
        d = datetime(year, month, day)
        schedule = CLASS_SCHEDULE.get(d.weekday())
        if not schedule:
            continue
        if d.date() == now.date() and now.time() < schedule[0]:
            continue  # today's class has not started yet
        count += 1

    return max(count, 1)
