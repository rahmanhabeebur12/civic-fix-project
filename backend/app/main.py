import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import Base, engine
from app.routers import (
    accessibility, analytics, auth, citizen, dashboard, departments, health, issues, notifications,
)
from app.services.antivirus_service import log_antivirus_status

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("civicfix")

Base.metadata.create_all(bind=engine)
log_antivirus_status()

app = FastAPI(title="CivicFix API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.CORS_ORIGINS],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def uploads_security_headers(request: Request, call_next):
    """Only sanitized images are ever written under UPLOAD_DIR (see
    app/services/image_sanitizer.py), but we still serve them defensively:
    fixed inline disposition and no MIME-sniffing, so a browser can never
    be tricked into treating an image response as executable/HTML content."""
    response = await call_next(request)
    if request.url.path.startswith("/uploads/"):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Disposition"] = "inline"
        response.headers["Content-Security-Policy"] = "default-src 'none'; sandbox"
    return response


app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Something went wrong on our end. Please try again."})


app.include_router(health.router)
app.include_router(auth.router)
app.include_router(citizen.router)
app.include_router(issues.public_router)
app.include_router(issues.staff_router)
app.include_router(departments.router)
app.include_router(dashboard.router)
app.include_router(analytics.router)
app.include_router(notifications.router)
app.include_router(accessibility.router)


@app.get("/")
def root():
    return {"name": "CivicFix API", "status": "running", "docs": "/docs"}
