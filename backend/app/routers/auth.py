import re

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.issue import Issue, IssueReport
from app.models.staff import StaffUser
from app.models.user import User
from app.schemas.auth import (
    CitizenAuthResponse, CitizenLoginRequest, CitizenProfileResponse, CitizenRegisterRequest,
    LoginRequest, LoginResponse, StaffProfile,
)
from app.services.auth_service import create_access_token, hash_password, verify_password
from app.services.reliability_service import compute_reliability
from app.utils.deps import get_current_citizen, get_current_staff

router = APIRouter(prefix="/auth", tags=["auth"])

_MOBILE_PATTERN = re.compile(r"^\d{10}$")


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    staff = db.query(StaffUser).filter(StaffUser.username == payload.username).first()
    if not staff or not verify_password(payload.password, staff.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")

    token = create_access_token({"sub": staff.username, "role": staff.role})
    return LoginResponse(
        access_token=token,
        username=staff.username,
        full_name=staff.full_name,
        role=staff.role,
        department=staff.department.name if staff.department else None,
    )


@router.get("/me", response_model=StaffProfile)
def me(staff: StaffUser = Depends(get_current_staff)):
    return StaffProfile(
        username=staff.username,
        full_name=staff.full_name,
        role=staff.role,
        department=staff.department.name if staff.department else None,
    )


# ---------------------------------------------------------------------------
# Citizen login/register — reuses the exact same JWT/password architecture
# as staff auth above (auth_service.hash_password/verify_password/
# create_access_token). Citizen tokens carry "type": "citizen" so they can
# never be mistaken for a staff token by get_current_citizen.
#
# Guest reporting (POST /citizen/reports with just name+mobile, no
# password) is completely untouched — a citizen who never registers can
# keep reporting exactly as before. Registering with a mobile number that
# already has report history (created as a guest) "claims" that existing
# User row rather than creating a duplicate identity, so past reports
# show up immediately once logged in.
# ---------------------------------------------------------------------------

@router.post("/citizen/register", response_model=CitizenAuthResponse)
def citizen_register(payload: CitizenRegisterRequest, db: Session = Depends(get_db)):
    mobile = payload.mobile.strip()
    name = payload.name.strip()
    if not _MOBILE_PATTERN.match(mobile):
        raise HTTPException(status_code=400, detail="Please enter a valid 10-digit mobile number.")
    if len(name) < 2:
        raise HTTPException(status_code=400, detail="Please enter your name.")
    if len(payload.password) < 4:
        raise HTTPException(status_code=400, detail="Please choose a password with at least 4 characters.")

    user = db.query(User).filter(User.mobile == mobile).first()
    if user and user.password_hash:
        raise HTTPException(status_code=400, detail="An account already exists for this number. Please log in instead.")

    if user:
        user.name = name
        user.password_hash = hash_password(payload.password)
    else:
        user = User(name=name, mobile=mobile, password_hash=hash_password(payload.password))
        db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token({"sub": user.mobile, "type": "citizen"})
    return CitizenAuthResponse(access_token=token, name=user.name, mobile=user.mobile)


@router.post("/citizen/login", response_model=CitizenAuthResponse)
def citizen_login(payload: CitizenLoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.mobile == payload.mobile.strip()).first()
    if not user or not user.password_hash or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Login failed. Please check your details.")

    token = create_access_token({"sub": user.mobile, "type": "citizen"})
    return CitizenAuthResponse(access_token=token, name=user.name, mobile=user.mobile)


@router.get("/citizen/me", response_model=CitizenProfileResponse)
def citizen_me(user: User = Depends(get_current_citizen), db: Session = Depends(get_db)):
    reports = db.query(IssueReport).filter(IssueReport.user_id == user.id).all()

    seen_issue_ids: set[int] = set()
    resolved_reports = 0
    supported_issues = sum(1 for r in reports if r.is_duplicate)
    for r in reports:
        if not r.issue_id or r.issue_id in seen_issue_ids:
            continue
        seen_issue_ids.add(r.issue_id)
        issue = db.query(Issue).get(r.issue_id)
        if issue and issue.status == "RESOLVED":
            resolved_reports += 1

    # Trust context only — see reliability_service.py. Never read by
    # app.services.core.priority.
    reliability = compute_reliability(db, user.id)

    return CitizenProfileResponse(
        name=user.name,
        mobile=user.mobile,
        total_reports=len(reports),
        resolved_reports=resolved_reports,
        supported_issues=supported_issues,
        reliability_label=reliability.label,
    )
