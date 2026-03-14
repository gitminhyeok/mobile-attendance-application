import logging
from contextlib import asynccontextmanager
import os
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from database import initialize_firebase, get_db
from routers import auth, attendance, views, admin

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Rate limiter
limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    initialize_firebase()
    logger.info("Application started successfully")
    yield
    # Shutdown
    logger.info("Application shutting down")


app = FastAPI(title="Magnus Attendance", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Include Routers
app.include_router(views.router)
app.include_router(auth.router)
app.include_router(attendance.router)
app.include_router(admin.router)


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception on {request.method} {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(status_code=500, content={"message": "Internal server error"})


# Health check endpoint
@app.get("/health")
async def health():
    db = get_db()
    return {"status": "ok", "database": "connected" if db else "disconnected"}

# Vercel Cron job endpoint
@app.get("/api/cron")
async def run_cron_job(authorization: str = Header(None)):
    expected_secret = os.getenv("CRON_SECRET")

    if not expected_secret or authorization != f"Bearer {expected_secret}":
        logger.warning("Unauthorized cron attempt")
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    db = get_db()
    logger.info("Cron job executed. Server is warmed up.")
    return {
        "ok": True,
        "message": "Server warmed up successfuly",
        "database": "connected" if db else "disconnected"
    }

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")
