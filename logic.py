import os
from datetime import datetime, time, timedelta
import pytz
from dotenv import load_dotenv

load_dotenv()

# Constants
KST = pytz.timezone('Asia/Seoul')
ALLOWED_IP = os.getenv("ALLOWED_IP", "127.0.0.1") 
# Example: "211.111.111.111"

def check_ip(client_ip: str) -> bool:
    """
    Check if the client IP matches the allowed gym IP.
    """
    # For local development, allow localhost
    if client_ip == "127.0.0.1" or client_ip == "::1":
        return True
    return client_ip == ALLOWED_IP

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
        return "closed", "오늘은 출석하는 날이 아닙니다 (주말만 가능)."

    current_time = now.time()
    
    if weekday == 5: # Saturday
        # 13:00 기준
        # 출석: 12:50 ~ 13:10
        # 지각: 13:10:01 ~ 13:30
        start_attend = time(12, 50)
        end_attend = time(13, 10)
        end_late = time(13, 30)
        
        if start_attend <= current_time <= end_attend:
            return "open", "출석 가능"
        elif end_attend < current_time <= end_late:
            return "late", "지각"
        else:
            return "closed", "출석 시간이 아닙니다."

    elif weekday == 6: # Sunday
        # 16:00 기준
        # 출석: 15:50 ~ 16:10
        # 지각: 16:10:01 ~ 16:30
        start_attend = time(15, 50)
        end_attend = time(16, 10)
        end_late = time(16, 30)

        if start_attend <= current_time <= end_attend:
            return "open", "출석 가능"
        elif end_attend < current_time <= end_late:
            return "late", "지각"
        else:
            return "closed", "출석 시간이 아닙니다."
            
    return "closed", "오류 발생"
