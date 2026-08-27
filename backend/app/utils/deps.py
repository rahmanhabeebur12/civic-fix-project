from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.staff import StaffUser
from app.models.user import User
from app.services.auth_service import decode_access_token

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_staff(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> StaffUser:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    payload = decode_access_token(credentials.credentials)
    if not payload or "sub" not in payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired session")

    staff = db.query(StaffUser).filter(StaffUser.username == payload["sub"]).first()
    if not staff:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Staff account not found")

    return staff


def require_admin(staff: StaffUser = Depends(get_current_staff)) -> StaffUser:
    if staff.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return staff


def get_current_citizen(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Same JWT architecture as get_current_staff, scoped to citizen
    tokens via the "type": "citizen" claim (see auth_service.create_access_token
    calls in routers/auth.py) so a staff token can never be reused here,
    even if a staff username happened to collide with a citizen mobile."""
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not logged in")

    payload = decode_access_token(credentials.credentials)
    if not payload or payload.get("type") != "citizen" or "sub" not in payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired session")

    user = db.query(User).filter(User.mobile == payload["sub"]).first()
    if not user or not user.password_hash:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account not found")

    return user
