from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from database import initialize_firebase
from routers import auth, attendance, views, admin

app = FastAPI(title="Magnus Attendance")

# Include Routers
app.include_router(views.router) # Views first to capture root
app.include_router(auth.router)
app.include_router(attendance.router)
app.include_router(admin.router)

# Initialize Firebase on startup
@app.on_event("startup")
async def startup_event():
    initialize_firebase()

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")
