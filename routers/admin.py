from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from database import get_db
from logic import get_current_kst_time
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
from google.cloud.firestore_v1.base_query import FieldFilter

load_dotenv()

router = APIRouter()
templates = Jinja2Templates(directory="templates")

# Get admin UIDs and clean them up
ADMIN_UIDS = [str(uid).strip() for uid in os.getenv("ADMIN_UID", "").split(",") if uid.strip()]

def is_admin(request: Request):
    uid = request.cookies.get("user_uid")
    
    # Debugging Logs
    print(f"--- Admin Check ---")
    print(f"Cookie UID: '{uid}' (Type: {type(uid)})")
    print(f"Authorized UIDs: {ADMIN_UIDS}")
    
    if not uid:
        print("Result: No UID in cookie.")
        return False
        
    if str(uid).strip() not in ADMIN_UIDS:
        print("Result: UID not in authorized list.")
        return False
        
    print("Result: Authorized!")
    return True

@router.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    if not is_admin(request):
        return RedirectResponse("/") # Or 403 Forbidden

    db = get_db()
    if not db:
        return HTMLResponse("Database Error", status_code=500)

    # Logic:
    # 1. Get all users
    # 2. For each user, find last attendance date
    # 3. Calculate days since last attendance
    # 4. Categorize: Normal, Warning (>=14 days), Dropout (>=21 days)
    
    users_ref = db.collection("users").stream()
    warning_list = []
    dropout_list = []
    
    now = get_current_kst_time()
    today = now.date() # Compare dates only
    
    for user_doc in users_ref:
        user_data = user_doc.to_dict()
        uid = user_data.get("uid")
        nickname = user_data.get("nickname", "Unknown")
        
        # Get last attendance
        # Optimization: Store 'last_attendance_date' in user doc to avoid heavy query.
        # Since we don't have it yet, we query attendance sorted by date desc limit 1.
        
        last_attend_doc = (
            db.collection("attendance")
            .where(filter=FieldFilter("user_id", "==", uid))
            .order_by("date", direction="DESCENDING")
            .limit(1)
            .stream()
        )
        
        last_date = None
        days_absent = 0
        
        # Convert generator to list to check if empty
        last_attend_list = list(last_attend_doc)
        
        if last_attend_list:
            data = last_attend_list[0].to_dict()
            date_str = data['date']
            last_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            days_absent = (today - last_date).days
        else:
            # No attendance ever. Use created_at or default huge number?
            # Let's say 999 days if never attended.
            days_absent = 999
            last_date = "Never"

        user_info = {
            "uid": uid,
            "nickname": nickname,
            "days_absent": days_absent,
            "last_date": last_date
        }

        if days_absent >= 21:
            dropout_list.append(user_info)
        elif days_absent >= 14:
            warning_list.append(user_info)
            
    # Sort by nickname ascending (Korean alphabetical order)
    dropout_list.sort(key=lambda x: x['nickname'])
    warning_list.sort(key=lambda x: x['nickname'])

    context = {
        "request": request,
        "warning_list": warning_list,
        "dropout_list": dropout_list,
        "total_warning": len(warning_list),
        "total_dropout": len(dropout_list)
    }
    return templates.TemplateResponse("admin/dashboard.html", context)
