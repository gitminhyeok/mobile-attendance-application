from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import os

app = FastAPI(title="Magnus Attendance")

# Setup templates (assumes a 'templates' directory exists)
# templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def read_root():
    return """
    <html>
        <head>
            <title>Magnus Attendance</title>
        </head>
        <body>
            <h1>Magnus Attendance App is Running!</h1>
        </body>
    </html>
    """
