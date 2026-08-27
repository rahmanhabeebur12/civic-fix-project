from sqlalchemy.orm import Session

from app.models.department import Department
from app.services.taxonomy import ISSUE_TYPES


def get_or_create_department(db: Session, name: str) -> Department:
    dept = db.query(Department).filter(Department.name == name).first()
    if dept:
        return dept
    code = "".join(w[0] for w in name.split() if w.isalnum()).upper()[:10] or "GEN"
    dept = Department(name=name, code=code)
    db.add(dept)
    db.flush()
    return dept


def route_department(db: Session, issue_type: str) -> tuple[Department, Department | None]:
    cfg = ISSUE_TYPES.get(issue_type, ISSUE_TYPES["Other"])
    primary = get_or_create_department(db, cfg["department"])

    supporting = None
    if issue_type in ("Fallen Tree", "Dangerous Tree Branch"):
        supporting = get_or_create_department(db, "Roads / Public Works")
    elif issue_type in ("Illegal Dumping",):
        supporting = get_or_create_department(db, "Solid Waste Management")

    return primary, supporting
