from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    full_name: str
    role: str
    department: str | None = None


class StaffProfile(BaseModel):
    username: str
    full_name: str
    role: str
    department: str | None = None


class CitizenRegisterRequest(BaseModel):
    name: str
    mobile: str
    password: str


class CitizenLoginRequest(BaseModel):
    mobile: str
    password: str


class CitizenAuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    name: str
    mobile: str


class CitizenProfileResponse(BaseModel):
    name: str
    mobile: str
    total_reports: int
    resolved_reports: int
    supported_issues: int
    reliability_label: str  # NEW | BUILDING | TRUSTED — see reliability_service.py
