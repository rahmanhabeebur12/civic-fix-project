"""
Seed demo data: departments, staff users, points of interest, and a realistic
spread of civic issues across many categories/statuses/priorities so the
dashboard, map, analytics, and hotspot views all have something meaningful
to show during a demo.

Run with:  venv/bin/python -m app.seed
"""
import json
import os
import random
from datetime import datetime, timedelta

from PIL import Image, ImageDraw, ImageFont

from app.config import settings
from app.database import Base, SessionLocal, engine
from app.models.department import Department
from app.models.issue import Issue, IssueReport, PointOfInterest, StatusHistory
from app.models.resolution import Resolution
from app.models.staff import StaffUser
from app.models.user import User
from app.services import priority_engine
from app.services.auth_service import hash_password
from app.services.core import priority as core_priority
from app.services.core import validator as core_validator
from app.services.location_service import describe_location
from app.services.routing_service import route_department
from app.services.taxonomy import DEPARTMENTS, ISSUE_TYPES

random.seed(42)

CENTER_LAT = settings.CITY_CENTER_LAT
CENTER_LNG = settings.CITY_CENTER_LNG

COLORS = {
    "Roads": (120, 120, 120), "Solid Waste": (139, 115, 85), "Street Lighting": (255, 193, 7),
    "Drainage": (33, 150, 243), "Sewerage": (76, 60, 45), "Water Supply": (0, 172, 193),
    "Public Infrastructure": (158, 158, 158), "Traffic": (244, 67, 54), "Environment": (76, 175, 80),
    "Sanitation": (255, 152, 0), "Animal Welfare": (156, 39, 176), "Civic Enforcement": (96, 125, 139),
    "Other": (100, 100, 100),
}


def jitter(lat, lng, max_km=3.0):
    dlat = random.uniform(-max_km, max_km) / 111.0
    dlng = random.uniform(-max_km, max_km) / (111.0 * 0.97)
    return round(lat + dlat, 6), round(lng + dlng, 6)


def make_placeholder_image(path: str, label: str, color):
    img = Image.new("RGB", (640, 480), color)
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.load_default()
    except Exception:
        font = None
    draw.rectangle([20, 20, 620, 460], outline=(255, 255, 255), width=4)
    draw.text((40, 220), label, fill=(255, 255, 255), font=font)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img.save(path, "JPEG", quality=80)


def save_demo_image(subdir: str, filename: str, label: str, category: str) -> str:
    rel_path = f"{subdir}/{filename}"
    full_path = os.path.join(settings.UPLOAD_DIR, rel_path)
    make_placeholder_image(full_path, label, COLORS.get(category, (100, 100, 100)))
    return rel_path


def get_or_create_department(db, name):
    dept = db.query(Department).filter(Department.name == name).first()
    if dept:
        return dept
    code = "".join(w[0] for w in name.split() if w.isalnum()).upper()[:10]
    dept = Department(name=name, code=code)
    db.add(dept)
    db.flush()
    return dept


def seed_departments(db):
    for name, code in DEPARTMENTS:
        if not db.query(Department).filter(Department.name == name).first():
            db.add(Department(name=name, code=code))
    db.commit()


def seed_staff(db):
    demo_staff = [
        ("admin", "admin123", "System Administrator", "admin", None),
        ("roads", "roads123", "Ravi Kumar", "officer", "Roads / Public Works"),
        ("sanitation", "sanitation123", "Priya Selvam", "officer", "Solid Waste Management"),
        ("electrical", "electrical123", "Arun Prakash", "officer", "Street Lighting / Electrical"),
        ("drainage", "drainage123", "Meena Raj", "officer", "Storm Water Drainage"),
    ]
    for username, password, full_name, role, dept_name in demo_staff:
        if db.query(StaffUser).filter(StaffUser.username == username).first():
            continue
        dept = get_or_create_department(db, dept_name) if dept_name else None
        db.add(StaffUser(
            username=username, password_hash=hash_password(password), full_name=full_name,
            role=role, department_id=dept.id if dept else None,
        ))
    db.commit()


def seed_pois(db):
    if db.query(PointOfInterest).count() > 0:
        return
    pois = [
        ("Chennai Corporation Higher Secondary School", "school", *jitter(CENTER_LAT, CENTER_LNG, 1.5)),
        ("Government General Hospital", "hospital", *jitter(CENTER_LAT, CENTER_LNG, 1.2)),
        ("Central Bus Terminus", "bus_stop", *jitter(CENTER_LAT, CENTER_LNG, 0.8)),
        ("Chrompet Railway Station", "railway_station", *jitter(CENTER_LAT, CENTER_LNG, 2.0)),
        ("Koyambedu Market", "market", *jitter(CENTER_LAT, CENTER_LNG, 1.8)),
        ("Municipal Corporation Office", "government_office", *jitter(CENTER_LAT, CENTER_LNG, 0.5)),
        ("Anna Salai Main Road", "main_road", *jitter(CENTER_LAT, CENTER_LNG, 1.0)),
        ("Metro Transport Hub", "transport_hub", *jitter(CENTER_LAT, CENTER_LNG, 1.3)),
        ("St. Mary's Primary School", "school", *jitter(CENTER_LAT, CENTER_LNG, 2.5)),
    ]
    for name, poi_type, lat, lng in pois:
        db.add(PointOfInterest(name=name, poi_type=poi_type, latitude=lat, longitude=lng))
    db.commit()


def plausible_validity_breakdown(score: float) -> dict:
    """Builds a breakdown shaped exactly like validator.calculate_validity()'s
    output — same six factors/weights — so seeded demo records render
    identically to live ones in the admin Validation section."""
    breakdown = {}
    for factor, weight in core_validator.SCORING_WEIGHTS.items():
        factor_score = round(min(100, max(0, score + random.uniform(-8, 8))), 2)
        breakdown[factor] = {
            "score": factor_score,
            "weight": weight,
            "weighted_contribution": round(factor_score * weight, 2),
        }
    return breakdown


def get_or_create_user(db, name, mobile):
    user = db.query(User).filter(User.mobile == mobile).first()
    if user:
        return user
    user = User(name=name, mobile=mobile)
    db.add(user)
    db.flush()
    return user


def create_issue(
    db, *, issue_type, description, lat, lng, reporter_count=1, status="SUBMITTED",
    validity_score=95, hours_ago=2, reporter_name="Demo Citizen", mobile_suffix="0001",
    with_resolution=False, resolution_confirmed=None, reopen=False,
):
    cfg = ISSUE_TYPES[issue_type]
    created_at = datetime.utcnow() - timedelta(hours=hours_ago)

    location = describe_location(db, lat, lng)
    severity_result = priority_engine.infer_severity(issue_type, description, location.location_context)
    impact_level = priority_engine.infer_impact_level(issue_type, severity_result.severity)
    primary_dept, supporting_dept = route_department(db, issue_type)

    # Same VALID/REVIEW/SUSPICIOUS thresholds as app.services.core.validator.
    validity_status = "VALID" if validity_score >= 80 else "REVIEW" if validity_score >= 60 else "SUSPICIOUS"

    from app.utils.id_generator import generate_complaint_id
    complaint_id = generate_complaint_id(db)

    image_path = save_demo_image("reports", f"{complaint_id}.jpg", issue_type, cfg["category"])

    issue = Issue(
        complaint_id=complaint_id, issue_type=issue_type, category=cfg["category"], is_demo=True,
        latitude=lat, longitude=lng,
        severity=severity_result.label, severity_level=severity_result.severity, severity_reason=severity_result.reason,
        impact_level=impact_level, location_type=location.location_type, location_context=location.location_context,
        primary_department_id=primary_dept.id, supporting_department_id=supporting_dept.id if supporting_dept else None,
        ai_confidence=0.88, ai_reasoning=f"Matched keywords for '{issue_type}'.",
        status=status, validity_status=validity_status,
        duplicate_score=0, duplicate_confidence="NONE", duplicate_action="CREATE_NEW",
        reporter_count=reporter_count, image_path=image_path,
        created_at=created_at, updated_at=created_at, assigned_at=created_at,
    )
    db.add(issue)
    db.flush()

    # PRIORITY — the same canonical, unmodified app.services.core.priority
    # module used by the live report_pipeline.
    priority_result = core_priority.calculate_priority({
        "severity": issue.severity_level, "number_of_reporters": reporter_count,
        "location_type": issue.location_type, "created_at": created_at.isoformat(),
        "impact_level": issue.impact_level,
    })
    issue.priority_score = priority_result["priority_score"]
    issue.priority_level = priority_result["priority_level"]
    issue.priority_breakdown = json.dumps(priority_result["breakdown"])
    issue.priority_reasons = json.dumps(priority_result["reasons"])

    db.add(StatusHistory(issue_id=issue.id, status="SUBMITTED", changed_by="citizen", note="Report submitted by citizen.", timestamp=created_at))
    if status != "MANUAL_REVIEW":
        db.add(StatusHistory(issue_id=issue.id, status="AI_VERIFIED", changed_by="system", note=f"AI classified as {issue_type}.", timestamp=created_at))
        db.add(StatusHistory(issue_id=issue.id, status="ASSIGNED", changed_by="system", note=f"Routed to {primary_dept.name}.", timestamp=created_at))
    else:
        db.add(StatusHistory(issue_id=issue.id, status="MANUAL_REVIEW", changed_by="system", note=f"Flagged for manual review (validity score {validity_score}).", timestamp=created_at))

    for n in range(reporter_count):
        user = get_or_create_user(db, f"{reporter_name} {n+1}" if reporter_count > 1 else reporter_name, f"98765{mobile_suffix}{n}")
        r_lat, r_lng = jitter(lat, lng, 0.03) if n > 0 else (lat, lng)
        db.add(IssueReport(
            client_report_id=f"seed-{complaint_id}-{n}", is_demo=True, issue_id=issue.id, user_id=user.id,
            original_description=description, normalized_description=description,
            image_path=image_path, image_hash=f"seedhash-{complaint_id}-{n}",
            latitude=r_lat, longitude=r_lng, gps_accuracy=8.0, language="en",
            validity_score=validity_score, validity_status=validity_status,
            validity_breakdown=json.dumps(plausible_validity_breakdown(validity_score)),
            validation_errors=json.dumps([] if validity_score >= 60 else ["description appears irrelevant or too short"]),
            supplemental_flags=json.dumps(["No issues detected"] if validity_score >= 80 else ["Unusually high submission frequency (mock demo data)"]),
            submitted_at=created_at + timedelta(minutes=n),
        ))

    if status == "ACCEPTED":
        issue.accepted_at = created_at + timedelta(minutes=30)
        issue.accepted_by = "Demo Officer"
        db.add(StatusHistory(issue_id=issue.id, status="ACCEPTED", changed_by="Demo Officer", note="Officer accepted the issue.", timestamp=issue.accepted_at))
    elif status == "IN_PROGRESS":
        issue.accepted_at = created_at + timedelta(minutes=30)
        issue.accepted_by = "Demo Officer"
        issue.work_started_at = created_at + timedelta(hours=1)
        db.add(StatusHistory(issue_id=issue.id, status="ACCEPTED", changed_by="Demo Officer", note="Officer accepted the issue.", timestamp=issue.accepted_at))
        db.add(StatusHistory(issue_id=issue.id, status="IN_PROGRESS", changed_by="Demo Officer", note="Work started.", timestamp=issue.work_started_at))

    if with_resolution:
        issue.accepted_at = created_at + timedelta(minutes=30)
        issue.accepted_by = "Demo Officer"
        issue.work_started_at = created_at + timedelta(hours=1)
        resolved_time = created_at + timedelta(hours=hours_ago - 0.5 if hours_ago > 1 else 0.5)
        after_image = save_demo_image("resolutions", f"{complaint_id}-after.jpg", f"{issue_type} (Repaired)", cfg["category"])
        resolution = Resolution(
            issue_id=issue.id, officer_username="roads", image_path=after_image,
            note="Repair completed and affected area restored.", created_at=resolved_time,
        )
        db.add(StatusHistory(issue_id=issue.id, status="ACCEPTED", changed_by="Demo Officer", note="Officer accepted the issue.", timestamp=issue.accepted_at))
        db.add(StatusHistory(issue_id=issue.id, status="IN_PROGRESS", changed_by="Demo Officer", note="Work started.", timestamp=issue.work_started_at))
        db.add(StatusHistory(issue_id=issue.id, status="AWAITING_CITIZEN_VERIFICATION", changed_by="Demo Officer", note="Resolution evidence submitted.", timestamp=resolved_time))

        if resolution_confirmed is True:
            resolution.citizen_confirmed = True
            resolution.confirmed_at = resolved_time + timedelta(hours=2)
            issue.status = "RESOLVED"
            issue.resolved_at = resolution.confirmed_at
            db.add(StatusHistory(issue_id=issue.id, status="RESOLVED", changed_by="citizen", note="Citizen confirmed the issue was fixed.", timestamp=issue.resolved_at))
        elif reopen:
            resolution.citizen_confirmed = False
            resolution.citizen_feedback = "The problem is still there, not fully fixed."
            resolution.confirmed_at = resolved_time + timedelta(hours=2)
            issue.status = "REOPENED"
            issue.reopen_count = 1
            issue.priority_score = priority_engine.apply_reopen_boost(issue.priority_score, settings.REOPEN_PRIORITY_BOOST)
            issue.priority_level = core_priority.get_priority_level(issue.priority_score)
            db.add(StatusHistory(issue_id=issue.id, status="REOPENED", changed_by="citizen", note="Citizen reported the issue is still unresolved.", timestamp=resolution.confirmed_at))
        else:
            issue.status = "AWAITING_CITIZEN_VERIFICATION"
        db.add(resolution)

    return issue


def seed_issues(db):
    if db.query(Issue).count() > 0:
        return

    # Priority demo: LOW vs CRITICAL
    create_issue(db, issue_type="Broken Bench", description="The park bench near the entrance is broken and unsafe to sit on.",
                 lat=CENTER_LAT + 0.01, lng=CENTER_LNG + 0.01, reporter_count=1, status="ASSIGNED", hours_ago=5, mobile_suffix="1001")

    school_poi = db.query(PointOfInterest).filter(PointOfInterest.poi_type == "school").first()
    school_lat, school_lng = (school_poi.latitude, school_poi.longitude) if school_poi else jitter(CENTER_LAT, CENTER_LNG, 1.5)
    create_issue(db, issue_type="Missing Manhole Cover", description="Open manhole right beside the school gate, very dangerous for children.",
                 lat=school_lat + 0.0002, lng=school_lng + 0.0002, reporter_count=4, status="ASSIGNED", hours_ago=8, mobile_suffix="1002")

    # Online demo flow issue (broken streetlight -> resolved end to end at runtime, seed just base cases)
    lat1, lng1 = jitter(CENTER_LAT, CENTER_LNG, 1.0)
    create_issue(db, issue_type="Broken Streetlight", description="Streetlight has been off for a week on our street, very dark at night.",
                 lat=lat1, lng=lng1, reporter_count=2, status="IN_PROGRESS", hours_ago=20, mobile_suffix="1003")

    # Spam / authenticity demo
    lat2, lng2 = jitter(CENTER_LAT, CENTER_LNG, 1.0)
    create_issue(db, issue_type="Garbage Accumulation", description="test test asdf", lat=lat2, lng=lng2,
                 reporter_count=1, status="MANUAL_REVIEW", validity_score=35, hours_ago=1, mobile_suffix="1004")

    # Resolved with citizen confirmation
    lat3, lng3 = jitter(CENTER_LAT, CENTER_LNG, 1.0)
    create_issue(db, issue_type="Pothole", description="Large pothole on the main road causing traffic and accidents risk.",
                 lat=lat3, lng=lng3, reporter_count=6, status="RESOLVED", hours_ago=72,
                 mobile_suffix="1005", with_resolution=True, resolution_confirmed=True)

    # Resolved then reopened
    lat4, lng4 = jitter(CENTER_LAT, CENTER_LNG, 1.0)
    create_issue(db, issue_type="Water Leakage", description="Pipeline leaking continuously, wasting a lot of water.",
                 lat=lat4, lng=lng4, reporter_count=3, status="REOPENED", hours_ago=96,
                 mobile_suffix="1006", with_resolution=True, reopen=True)

    # Awaiting citizen verification
    lat5, lng5 = jitter(CENTER_LAT, CENTER_LNG, 1.0)
    create_issue(db, issue_type="Damaged Footpath", description="Footpath tiles broken and uneven, people keep tripping.",
                 lat=lat5, lng=lng5, reporter_count=2, status="AWAITING_CITIZEN_VERIFICATION", hours_ago=30,
                 mobile_suffix="1007", with_resolution=True)

    # Remaining required categories, single reports each, varied statuses
    remaining = [
        ("Overflowing Drain", "Drain is overflowing onto the road after every rain."),
        ("Sewage Overflow", "Sewage is overflowing near the residential block, terrible smell."),
        ("Fallen Tree", "A large tree has fallen and is blocking the road completely."),
        ("Traffic Signal Failure", "Traffic signal at the junction has stopped working, causing chaos."),
        ("Illegal Dumping", "People are dumping construction waste illegally on the empty plot."),
        ("Exposed Electrical Wire", "Live wire hanging low near the bus stop, extremely dangerous."),
        ("Public Toilet Issue", "Public toilet is unusable, no water and very unhygienic."),
        ("Stray Animal Issue", "A pack of stray dogs is aggressive towards pedestrians in the evening."),
        ("Construction Debris", "Construction debris dumped on the roadside is blocking pedestrian movement."),
        ("Broken Road", "Road surface broken for over 100 meters near the market."),
        ("Damaged Manhole", "Manhole cover cracked and sinking, risk to two-wheelers."),
        ("Flickering Streetlight", "Streetlight flickers constantly and may fail soon."),
        ("Encroachment", "Shop has encroached onto the public footpath blocking pedestrians."),
    ]
    statuses_cycle = ["SUBMITTED", "AI_VERIFIED", "ASSIGNED", "ACCEPTED", "IN_PROGRESS"]
    for idx, (itype, desc) in enumerate(remaining):
        if itype not in ISSUE_TYPES:
            itype = "Other"
        r_lat, r_lng = jitter(CENTER_LAT, CENTER_LNG, 2.5)
        create_issue(
            db, issue_type=itype, description=desc, lat=r_lat, lng=r_lng,
            reporter_count=random.randint(1, 5), status=statuses_cycle[idx % len(statuses_cycle)],
            validity_score=random.choice([90, 92, 96, 65, 88]), hours_ago=random.randint(1, 60), mobile_suffix=f"2{idx:03d}",
        )

    # Recurring drainage hotspot cluster — several nearby drainage issues over time
    hotspot_lat, hotspot_lng = jitter(CENTER_LAT, CENTER_LNG, 2.0)
    hotspot_days_ago_hours = [24 * 80, 24 * 60, 24 * 40, 24 * 20, 24 * 5]
    for i, hrs in enumerate(hotspot_days_ago_hours):
        h_lat, h_lng = jitter(hotspot_lat, hotspot_lng, 0.15)
        create_issue(
            db, issue_type="Overflowing Drain", description="Recurring drainage overflow at Demo Junction after every rain.",
            lat=h_lat, lng=h_lng,
            reporter_count=random.randint(2, 6), status="RESOLVED" if i < 4 else "ASSIGNED",
            hours_ago=hrs, mobile_suffix=f"3{i:03d}",
            with_resolution=(i < 4), resolution_confirmed=(i < 4),
        )

    db.commit()


def run_seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_departments(db)
        seed_staff(db)
        seed_pois(db)
        seed_issues(db)
        print("Seed complete.")
    finally:
        db.close()


if __name__ == "__main__":
    run_seed()
