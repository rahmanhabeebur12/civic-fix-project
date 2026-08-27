import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import Base, SessionLocal, engine
from app.routers import (
    accessibility, analytics, auth, citizen, dashboard, departments, health, issues, notifications,
)
from app.services.antivirus_service import log_antivirus_status

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("civicfix")

Base.metadata.create_all(bind=engine)


def _ensure_default_staff_accounts() -> None:
    """A brand-new database (e.g. a fresh Render PostgreSQL instance) has
    tables but no rows -- create_all() above only creates the schema.
    Without this, staff/admin login doesn't fail because of a wrong
    password; the account simply never existed. seed_departments() and
    seed_staff() are the same functions the local `python -m app.seed`
    workflow already uses -- both idempotent (skip anything that already
    exists) and both hash passwords via app.services.auth_service, so
    this is safe to run on every startup and never creates duplicates or
    stores a plaintext password. Deliberately excludes seed_pois/
    seed_issues (the demo dataset) -- this only guarantees the login
    accounts exist, not a full demo dataset on every deploy."""
    from app.seed import seed_departments, seed_staff

    db = SessionLocal()
    try:
        seed_departments(db)
        seed_staff(db)
    finally:
        db.close()


_ensure_default_staff_accounts()
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
