import os
import logging
import httpx
from fastapi import APIRouter, Request, Response, HTTPException
from fastapi.responses import RedirectResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from dotenv import load_dotenv
from database import get_db
from dependencies import sign_uid, COOKIE_MAX_AGE
from firebase_admin import firestore

load_dotenv()

logger = logging.getLogger(__name__)

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)

KAKAO_CLIENT_ID = os.getenv("KAKAO_CLIENT_ID")
KAKAO_REDIRECT_URI = os.getenv("KAKAO_REDIRECT_URI")


@router.get("/login/kakao")
@limiter.limit("10/minute")
def login_kakao(request: Request):
    client_id = os.getenv("KAKAO_CLIENT_ID")
    redirect_uri = os.getenv("KAKAO_REDIRECT_URI")

    if not client_id or "your_kakao_client_id" in client_id:
        logger.error("Kakao Client ID is missing or default in .env")
        raise HTTPException(status_code=500, detail="Server Configuration Error: Kakao Client ID missing.")

    url = f"https://kauth.kakao.com/oauth/authorize?client_id={client_id}&redirect_uri={redirect_uri}&response_type=code"
    return RedirectResponse(url)


@router.get("/auth/kakao/callback")
@limiter.limit("10/minute")
async def kakao_callback(request: Request, code: str, response: Response):
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
        logger.debug(f"Requesting token with redirect_uri={redirect_uri}")
        async with httpx.AsyncClient() as client:
            token_res = await client.post(token_url, data=payload)

        if token_res.status_code != 200:
            logger.error(f"Token Request Failed. Status: {token_res.status_code}, Body: {token_res.text}")
            raise HTTPException(status_code=400, detail="Kakao Login Failed (Token)")

        token_json = token_res.json()
        access_token = token_json.get("access_token")
    except httpx.HTTPError as e:
        logger.exception(f"HTTP error during token exchange: {e}")
        raise HTTPException(status_code=400, detail=f"Failed to get access token: {str(e)}")

    # 2. Get User Info
    user_url = "https://kapi.kakao.com/v2/user/me"
    headers = {"Authorization": f"Bearer {access_token}"}

    try:
        async with httpx.AsyncClient() as client:
            user_res = await client.get(user_url, headers=headers)
        user_res.raise_for_status()
        user_info = user_res.json()
    except httpx.HTTPError as e:
        logger.exception(f"Failed to get user info: {e}")
        raise HTTPException(status_code=400, detail=f"Failed to get user info: {str(e)}")

    # 3. Process User Data
    kakao_uid = str(user_info.get("id"))
    kakao_account = user_info.get("kakao_account", {})
    profile = kakao_account.get("profile", {})
    properties = user_info.get("properties", {})

    # Priority: Profile Nickname (Real) > Properties Nickname > Default
    nickname = profile.get("nickname") or properties.get("nickname") or f"User{kakao_uid}"
    profile_image = profile.get("profile_image_url") or properties.get("profile_image", "")

    # Validate profile image URL
    if profile_image and not profile_image.startswith("https://"):
        profile_image = ""

    logger.info(f"Logged in as {nickname} ({kakao_uid})")

    # 4. Save/Update in Firebase
    db = get_db()
    if db:
        user_ref = db.collection("users").document(kakao_uid)
        user_doc = user_ref.get()

        if not user_doc.exists:
            # New User: Store initial info
            user_data = {
                "uid": kakao_uid,
                "nickname": nickname,
                "initial_nickname": nickname,
                "profile_image": profile_image,
                "created_at": firestore.SERVER_TIMESTAMP,
                "last_login": firestore.SERVER_TIMESTAMP,
                "is_auth": "pending"
            }
            user_ref.set(user_data)
        else:
            # Existing User: Update profile image and last login only
            user_data = user_doc.to_dict()
            update_data = {
                "profile_image": profile_image,
                "last_login": firestore.SERVER_TIMESTAMP
            }

            # If user was 'withdrawn', set to 'pending' to require re-approval
            if user_data.get("is_auth") == "withdrawn":
                update_data["is_auth"] = "pending"

            user_ref.update(update_data)

    # 5. Create Signed Session Cookie
    signed_value = sign_uid(kakao_uid)
    response = RedirectResponse(url="/")
    response.set_cookie(
        key="user_uid",
        value=signed_value,
        httponly=True,
        max_age=COOKIE_MAX_AGE,
        samesite="lax",
    )
    return response


@router.get("/logout")
def logout(response: Response):
    response = RedirectResponse(url="/")
    response.delete_cookie("user_uid")
    return response
