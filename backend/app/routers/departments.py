from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.department import Department

router = APIRouter(prefix="/departments", tags=["departments"])


@router.get("")
def list_departments(db: Session = Depends(get_db)):
    depts = db.query(Department).order_by(Department.name).all()
    return [{"id": d.id, "name": d.name, "code": d.code} for d in depts]
