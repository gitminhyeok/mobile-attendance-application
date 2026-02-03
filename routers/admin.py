from fastapi import APIRouter, Request, HTTPException, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from database import get_db
from logic import get_current_kst_time
from datetime import datetime, timedelta
import os
import re
from dotenv import load_dotenv
from google.cloud.firestore_v1.base_query import FieldFilter
from pydantic import BaseModel
from typing import List
from firebase_admin import firestore

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

class BatchAttendanceRequest(BaseModel):
    date: str
    user_ids: List[str]
    status: str # 'present', 'late', 'absent'

@router.get("/admin/api/attendance/daily")
async def get_daily_attendance(request: Request, date: str):
    if not is_admin(request):
        return JSONResponse(status_code=403, content={"message": "Unauthorized"})
    
    db = get_db()
    if not db:
        return JSONResponse(status_code=500, content={"message": "Database error"})

    # Query all attendance for this date
    docs = db.collection("attendance").where(filter=FieldFilter("date", "==", date)).stream()
    
    result = {}
    for doc in docs:
        data = doc.to_dict()
        result[data['user_id']] = data['status']
        
    return JSONResponse(result)

@router.post("/admin/api/attendance/batch")
async def batch_update_attendance(request: Request, payload: BatchAttendanceRequest):
    if not is_admin(request):
        return JSONResponse(status_code=403, content={"message": "Unauthorized"})
    
    db = get_db()
    if not db:
        return JSONResponse(status_code=500, content={"message": "Database error"})
        
    updated_count = 0
    
    for uid in payload.user_ids:
        # Check existing
        docs = (
            db.collection("attendance")
            .where(filter=FieldFilter("user_id", "==", uid))
            .where(filter=FieldFilter("date", "==", payload.date))
            .limit(1)
            .stream()
        )
        existing_doc = next(docs, None)
        
        if payload.status == 'absent':
            if existing_doc:
                existing_doc.reference.delete()
                updated_count += 1
        else:
            # present or late
            if existing_doc:
                # Update status if changed
                if existing_doc.to_dict().get('status') != payload.status:
                    existing_doc.reference.update({"status": payload.status})
                    updated_count += 1
            else:
                # Create new
                new_data = {
                    "user_id": uid,
                    "date": payload.date,
                    "timestamp": firestore.SERVER_TIMESTAMP,
                    "status": payload.status
                }
                db.collection("attendance").add(new_data)
                updated_count += 1

    return JSONResponse(status_code=200, content={"message": f"Processed {updated_count} updates."})

@router.post("/admin/api/user/delete")
async def delete_user(request: Request, uid: str = Form(...)):
    if not is_admin(request):
        return JSONResponse(status_code=403, content={"message": "Unauthorized"})
    
    db = get_db()
    if not db:
        return JSONResponse(status_code=500, content={"message": "Database error"})

    # 1. Delete Attendance Records
    attendance_docs = db.collection("attendance").where(filter=FieldFilter("user_id", "==", uid)).stream()
    deleted_attendance = 0
    batch = db.batch()
    
    for doc in attendance_docs:
        batch.delete(doc.reference)
        deleted_attendance += 1
        
        # Commit every 400 ops to stay safe within limit (500)
        if deleted_attendance % 400 == 0:
            batch.commit()
            batch = db.batch()
            
    batch.commit() # Commit remaining
    
    # 2. Delete User
    db.collection("users").document(uid).delete()
    
    return JSONResponse(status_code=200, content={"message": f"User and {deleted_attendance} attendance records deleted."})

@router.post("/admin/api/user/update")
async def update_user_info(
    request: Request,
    uid: str = Form(...),
    nickname: str = Form(None),
    phone: str = Form(None),
    batch: str = Form(None),
    is_auth: str = Form(None), # Changed from status
    unnotified_date1: str = Form(""),
    unnotified_date2: str = Form(""),
    is_sick_leave: bool = Form(False)
):
    if not is_admin(request):
        return JSONResponse(status_code=403, content={"message": "Unauthorized"})
    
    db = get_db()
    if not db:
        return JSONResponse(status_code=500, content={"message": "Database error"})

    update_data = {
        "unnotified_date1": unnotified_date1.strip(),
        "unnotified_date2": unnotified_date2.strip(),
        "is_sick_leave": is_sick_leave
    }

    # 0. Auth Status Update
    if is_auth:
        update_data["is_auth"] = is_auth.strip()

    # 0. Nickname Update
    if nickname:
        update_data["nickname"] = nickname.strip()

    # 1. Phone Validation & Formatting
    if phone:
        raw_phone = re.sub(r'[^0-9]', '', phone)
        if raw_phone.startswith('010') and len(raw_phone) == 11:
             formatted_phone = f"{raw_phone[:3]}-{raw_phone[3:7]}-{raw_phone[7:]}"
             update_data["phone"] = formatted_phone
        elif len(raw_phone) > 0:
             update_data["phone"] = phone
    
    # 2. Batch Validation & Formatting (YY-MM)
    if batch:
        clean_batch = batch.strip()
        match = re.match(r'^(\d{2,4})-(\d{1,2})$', clean_batch)
        if match:
            y, m = match.groups()
            y = y[-2:]
            m = m.zfill(2)
            update_data["batch"] = f"{y}-{m}"
        else:
            digits = re.sub(r'[^0-9]', '', clean_batch)
            if len(digits) == 4:
                update_data["batch"] = f"{digits[:2]}-{digits[2:]}"
            elif len(digits) == 6:
                update_data["batch"] = f"{digits[2:4]}-{digits[4:]}"
            else:
                update_data["batch"] = clean_batch
    else:
        update_data["batch"] = ""

    if update_data:
        user_ref = db.collection("users").document(uid)
        user_ref.set(update_data, merge=True)
        return JSONResponse(status_code=200, content={"message": "Updated successfully", "data": update_data})
    
    return JSONResponse(status_code=200, content={"message": "No changes made"})

@router.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    if not is_admin(request):
        return RedirectResponse("/") 

    uid = request.cookies.get("user_uid") # Get current admin's UID
    db = get_db()
    if not db:
        return HTMLResponse("Database Error", status_code=500)

    users_ref = db.collection("users").stream()
    warning_list = []
    dropout_list = []
    sick_list = []
    all_users_list = []
    pending_list = []
    
    now = get_current_kst_time()
    today = now.date()
    
    for user_doc in users_ref:
        user_data = user_doc.to_dict()
        user_id = user_data.get("uid")
        nickname = user_data.get("nickname", "Unknown")
        initial_nickname = user_data.get("initial_nickname", nickname)
        phone = user_data.get("phone", "")
        batch = user_data.get("batch", "")
        profile_image = user_data.get("profile_image", "")
        
        # Check is_auth first, then fallback to status, then default to approved
        is_auth = user_data.get("is_auth") or user_data.get("status", "approved")
        
        # New Fields for Unnotified Dates
        unnotified_date1 = user_data.get("unnotified_date1", "")
        unnotified_date2 = user_data.get("unnotified_date2", "")
        is_sick_leave = user_data.get("is_sick_leave", False)
        
        # Calculate count based on dates
        unnotified_count = 0
        if unnotified_date1: unnotified_count += 1
        if unnotified_date2: unnotified_count += 1
        
        # Get last attendance
        last_attend_doc = (
            db.collection("attendance")
            .where(filter=FieldFilter("user_id", "==", user_id))
            .order_by("date", direction="DESCENDING")
            .limit(1)
            .stream()
        )
        
        last_date_str = "Never"
        days_absent = -1 # New user / No attendance record
        
        last_attend_list = list(last_attend_doc)
        if last_attend_list:
            data = last_attend_list[0].to_dict()
            last_date_str = data['date']
            last_date = datetime.strptime(last_date_str, "%Y-%m-%d").date()
            days_absent = (today - last_date).days
            
        user_info = {
            "uid": user_id,
            "nickname": nickname,
            "initial_nickname": initial_nickname,
            "profile_image": profile_image,
            "days_absent": days_absent,
            "last_date": last_date_str,
            "phone": phone,
            "batch": batch,
            "unnotified_date1": unnotified_date1,
            "unnotified_date2": unnotified_date2,
            "unnotified_count": unnotified_count,
            "is_sick_leave": is_sick_leave,
            "is_auth": is_auth
        }
        
        if is_auth == 'pending':
            pending_list.append(user_info)
            continue 
        
        all_users_list.append(user_info)

        if is_sick_leave:
            sick_list.append(user_info)
        else:
            # Dropout Criteria: 21+ days OR 2 unnotified absences
            if days_absent >= 21 or unnotified_count >= 2:
                reasons = []
                if days_absent >= 21: reasons.append("장기 결석 (3주+)")
                if unnotified_count >= 2: reasons.append(f"미통보 불참 2회 ({unnotified_date1}, {unnotified_date2})")
                user_info['reason'] = " & ".join(reasons)
                dropout_list.append(user_info)
            
            # Warning Criteria: Only 14+ days absence
            elif days_absent >= 14:
                user_info['reason'] = "2주 이상 결석"
                warning_list.append(user_info)
            
    # Sorting
    dropout_list.sort(key=lambda x: x['nickname'])
    warning_list.sort(key=lambda x: x['nickname'])
    sick_list.sort(key=lambda x: x['nickname'])
    all_users_list.sort(key=lambda x: x['nickname'])
    pending_list.sort(key=lambda x: x['nickname'])

    # Group by Batch
    batch_groups = {}
    for user in all_users_list:
        b = user.get('batch')
        if not b:
            b = "No Batch"
        if b not in batch_groups:
            batch_groups[b] = []
        batch_groups[b].append(user)
    
    # Sort Batches: "No Batch" first, then Descending order (Latest first)
    def batch_sort_key(b_key):
        if b_key == "No Batch":
            return "ZZ-ZZ" # Force to top
        return b_key

    batch_list = []
    sorted_keys = sorted(batch_groups.keys(), key=batch_sort_key, reverse=True)
    
    for key in sorted_keys:
        batch_list.append({
            "name": key,
            "users": sorted(batch_groups[key], key=lambda u: u['nickname']), # Ensure name sort inside
            "count": len(batch_groups[key])
        })

    context = {
        "request": request,
        "uid": uid, 
        "is_admin_page": True, # Flag to hide Record/Ranking in nav
        "is_admin_user": True, # Flag to show ADMIN link
        "warning_list": warning_list,
        "dropout_list": dropout_list,
        "sick_list": sick_list,
        "all_users_list": all_users_list,
        "pending_list": pending_list,
        "batch_list": batch_list,
        "total_warning": len(warning_list),
        "total_dropout": len(dropout_list),
        "total_sick": len(sick_list),
        "total_users": len(all_users_list),
        "total_pending": len(pending_list)
    }
    return templates.TemplateResponse("admin/dashboard.html", context)
