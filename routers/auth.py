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
    client_id = os.getenv("KAKAO_CLIENT_ID")
    redirect_uri = os.getenv("KAKAO_REDIRECT_URI")

    if not client_id or "your_kakao_client_id" in client_id:
        print("ERROR: Kakao Client ID is missing or default in .env")
        raise HTTPException(status_code=500, detail="Server Configuration Error: Kakao Client ID missing.")
    
    url = f"https://kauth.kakao.com/oauth/authorize?client_id={client_id}&redirect_uri={redirect_uri}&response_type=code"
    return RedirectResponse(url)

@router.get("/auth/kakao/callback")
def allback(code: str, request: Request, response: Response):
    client_id = os.getenv("KAKAO_CLIENT_ID")
    redirect_uri = os.getenv("KAKAO_REDIRECT_URI")

    if not code:
        raise HTTPException(status_code=400, detail="Code not found")
    
    # 1. Get Access Token
    token_url = "https://kauth.kakao.com/oauth/token"
    payload = {
        "grant_type": "authorization_code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "code": code,
    }
    
    try:
        print(f"DEBUG: Requesting token with redirect_uri={redirect_uri}")
        token_res = requests.post(token_url, data=payload)
        
        if token_res.status_code != 200:
            print(f"ERROR: Token Request Failed. Status: {token_res.status_code}, Body: {token_res.text}")
            raise HTTPException(status_code=400, detail="Kakao Login Failed (Token)")
            
        token_json = token_res.json()
        access_token = token_json.get("access_token")
    except Exception as e:
        print(f"EXCEPTION: {str(e)}")
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
    kakao_account = user_info.get("kakao_account", {})
    profile = kakao_account.get("profile", {})
    properties = user_info.get("properties", {})
    
    # Priority: Profile Nickname (Real) > Properties Nickname > Default
    nickname = profile.get("nickname") or properties.get("nickname") or f"User{kakao_uid}"
    profile_image = profile.get("profile_image_url") or properties.get("profile_image", "")
    
    print(f"DEBUG: Logged in as {nickname} ({kakao_uid})")

    # 4. Save/Update in Firebase
    db = get_db()
    if db:
        user_ref = db.collection("users").document(kakao_uid)
        user_doc = user_ref.get()
        
        if not user_doc.exists:
            # New User: Store initial info
            user_data = {
                "uid": kakao_uid,
                "nickname": nickname, # Initial display name
                "initial_nickname": nickname, # Permanent record of original name
                "profile_image": profile_image,
                "created_at": firestore.SERVER_TIMESTAMP,
                "last_login": firestore.SERVER_TIMESTAMP
            }
            user_ref.set(user_data)
        else:
            # Existing User: Update profile image and last login only
            # Do NOT update nickname, as Admin might have changed it to a real name
            update_data = {
                "profile_image": profile_image,
                "last_login": firestore.SERVER_TIMESTAMP
            }
            user_ref.update(update_data)
        
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
