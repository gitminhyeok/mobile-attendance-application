from fastapi import APIRouter, Request, Response, HTTPException, Depends
from fastapi.responses import RedirectResponse
import os
import requests
from dotenv import load_dotenv
from database import get_db
from firebase_admin import firestore

load_dotenv()

router = APIRouter()

KAKAO_CLIENT_ID = os.getenv("KAKAO_CLIENT_ID")
KAKAO_REDIRECT_URI = os.getenv("KAKAO_REDIRECT_URI")
# KAKAO_CLIENT_SECRET = os.getenv("KAKAO_CLIENT_SECRET") # Optional

@router.get("/login/kakao")
def login_kakao():
    if not KAKAO_CLIENT_ID:
        raise HTTPException(status_code=500, detail="Kakao Client ID not configured")
    
    url = f"https://kauth.kakao.com/oauth/authorize?client_id={KAKAO_CLIENT_ID}&redirect_uri={KAKAO_REDIRECT_URI}&response_type=code"
    return RedirectResponse(url)

@router.get("/auth/kakao/callback")
def kakao_callback(code: str, request: Request, response: Response):
    if not code:
        raise HTTPException(status_code=400, detail="Code not found")
    
    # 1. Get Access Token
    token_url = "https://kauth.kakao.com/oauth/token"
    payload = {
        "grant_type": "authorization_code",
        "client_id": KAKAO_CLIENT_ID,
        "redirect_uri": KAKAO_REDIRECT_URI,
        "code": code,
        # "client_secret": KAKAO_CLIENT_SECRET
    }
    
    try:
        token_res = requests.post(token_url, data=payload)
        token_res.raise_for_status()
        token_json = token_res.json()
        access_token = token_json.get("access_token")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to get access token: {str(e)}")

    # 2. Get User Info
    user_url = "https://kapi.kakao.com/v2/user/me"
    headers = {"Authorization": f"Bearer {access_token}"}
    
    try:
        user_res = requests.get(user_url, headers=headers)
        user_res.raise_for_status()
        user_info = user_res.json()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to get user info: {str(e)}")

    # 3. Process User Data
    kakao_uid = str(user_info.get("id"))
    properties = user_info.get("properties", {})
    nickname = properties.get("nickname", f"User{kakao_uid}")
    profile_image = properties.get("profile_image", "")
    
    # 4. Save/Update in Firebase
    db = get_db()
    if db:
        user_ref = db.collection("users").document(kakao_uid)
        user_data = {
            "uid": kakao_uid,
            "nickname": nickname,
            "profile_image": profile_image,
            "last_login": firestore.SERVER_TIMESTAMP
        }
        # Use set with merge=True to update existing or create new
        user_ref.set(user_data, merge=True)
        
        # Check if created_at exists, if not add it (only for new users)
        # Note: set with merge doesn't easily allow "only if not exists" for one field without reading first.
        # For simplicity in this MVP, we just update basic info.
        
    # 5. Create Session (Simple Cookie for MVP)
    # In a real app, you'd generate a session ID or JWT and store it.
    # Here we'll just store the UID in a signed cookie or similar.
    response = RedirectResponse(url="/")
    response.set_cookie(key="user_uid", value=kakao_uid, httponly=True)
    return response

@router.get("/logout")
def logout(response: Response):
    response = RedirectResponse(url="/")
    response.delete_cookie("user_uid")
    return response
