from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import os

from .db.database import init_db
from .core.logging_conf import logger
from .api import auth, machines, groups, dashboard, system, commands, services_api, logs, files, audit, terminal, users_api, consoles, youtube

app = FastAPI(title="LAN SSH Manager", version="1.1.0")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

init_db()

app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(machines.router)
app.include_router(groups.router)
app.include_router(system.router)
app.include_router(commands.router)
app.include_router(services_api.router)
app.include_router(logs.router)
app.include_router(files.router)
app.include_router(audit.router)
app.include_router(terminal.router)
app.include_router(users_api.router)
app.include_router(consoles.router)
app.include_router(consoles.router_ws)
app.include_router(youtube.router)


@app.get("/api/health")
def health():
    return {"success": True, "data": {"status": "ok"}, "message": None}


FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "frontend")
# backend/app/main.py -> dirname x3 = project root/frontend
if os.path.isdir(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")
    vendor_dir = os.path.join(FRONTEND_DIR, "vendor")
    if os.path.isdir(vendor_dir):
        app.mount("/vendor", StaticFiles(directory=vendor_dir), name="vendor")


@app.get("/app.js", include_in_schema=False)
def app_js():
    return FileResponse(os.path.join(FRONTEND_DIR, "app.js"), media_type="application/javascript")


@app.get("/dailymotion.js", include_in_schema=False)
def dailymotion_js():
    return FileResponse(os.path.join(FRONTEND_DIR, "dailymotion.js"), media_type="application/javascript")


@app.get("/youtube.js", include_in_schema=False)
def youtube_js():
    return FileResponse(os.path.join(FRONTEND_DIR, "youtube.js"), media_type="application/javascript")


@app.get("/entertainment.js", include_in_schema=False)
def entertainment_js():
    return FileResponse(os.path.join(FRONTEND_DIR, "entertainment.js"), media_type="application/javascript")


@app.get("/entertainment.css", include_in_schema=False)
def entertainment_css():
    return FileResponse(os.path.join(FRONTEND_DIR, "entertainment.css"), media_type="text/css")


@app.get("/styles.css", include_in_schema=False)
def styles_css():
    return FileResponse(os.path.join(FRONTEND_DIR, "styles.css"), media_type="text/css")


@app.get("/")
def index():
    idx = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(idx):
        return FileResponse(idx)
    return {"success": True, "data": {"app": "LAN SSH Manager", "docs": "/docs"}, "message": None}


@app.on_event("startup")
def _startup():
    logger.info("LAN SSH Manager startup OK")
