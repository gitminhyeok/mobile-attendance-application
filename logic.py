import os
from datetime import datetime, time, timedelta
import pytz
from dotenv import load_dotenv

load_dotenv()

# Constants
KST = pytz.timezone('Asia/Seoul')
ALLOWED_IP = os.getenv("ALLOWED_IP", "127.0.0.1") 
# Example: "211.111.111.111"

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
    weekday = now.weekday() # Monday=0, Sunday=6
    
    # Saturday = 5, Sunday = 6
    if weekday not in [5, 6]:
        return "closed", "오늘은 훈련일이 아닙니다."

    current_time = now.time()
    
    if weekday == 5: # Saturday
        # 13:00 기준
        # 출석: 12:45 ~ 13:15 (전후 15분)
        # 지각: 13:15:01 ~ 15:00 (기준 시간 2시간까지)
        start_attend = time(12, 45)
        end_attend = time(13, 16)
        end_late = time(15, 0)
        
        if start_attend <= current_time <= end_attend:
            return "open", "출석 가능"
        elif end_attend < current_time <= end_late:
            return "late", "지각"
        else:
            return "closed", "출석 시간이 아닙니다."

    elif weekday == 6: # Sunday
        # 16:00 기준
        # 출석: 15:45 ~ 16:15 (전후 15분)
        # 지각: 16:15:01 ~ 18:00 (기준 시간 2시간까지)
        start_attend = time(12, 45)
        end_attend = time(16, 16)
        end_late = time(18, 0)

        if start_attend <= current_time <= end_attend:
            return "open", "출석 가능"
        elif end_attend < current_time <= end_late:
            return "late", "지각"
        else:
            return "closed", "출석 시간이 아닙니다."
            
    return "closed", "오류 발생"
