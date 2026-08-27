"""
Central, extensible civic-issue taxonomy.

Adding a new issue type later means adding one entry to ISSUE_TYPES —
nothing else in the application needs to change.

Each entry's "validator_category" maps our rich issue_type down to the
fixed category vocabulary that app/services/core/validator.py (the
canonical, unmodified validity engine) accepts. That module owns its own
VALID_CATEGORIES set — this mapping exists so any of our 40+ issue types
can be validated without ever touching validator.py itself.
"""

# Each entry: issue_type -> config
ISSUE_TYPES = {
    # Roads
    "Pothole": {"category": "Roads", "department": "Roads / Public Works", "keywords": ["pothole", "pot hole", "road hole"], "base_severity": "HIGH", "validator_category": "pothole"},
    "Broken Road": {"category": "Roads", "department": "Roads / Public Works", "keywords": ["broken road", "damaged road", "road damage"], "base_severity": "HIGH", "validator_category": "road_damage"},
    "Road Crack": {"category": "Roads", "department": "Roads / Public Works", "keywords": ["road crack", "crack in road", "cracked road"], "base_severity": "MEDIUM", "validator_category": "road_damage"},
    "Road Obstruction": {"category": "Roads", "department": "Roads / Public Works", "keywords": ["road block", "obstruction", "road obstacle"], "base_severity": "MEDIUM", "validator_category": "other"},

    # Waste
    "Garbage Accumulation": {"category": "Solid Waste", "department": "Solid Waste Management", "keywords": ["garbage", "waste", "trash", "rubbish", "litter"], "base_severity": "MEDIUM", "validator_category": "garbage"},
    "Uncollected Garbage": {"category": "Solid Waste", "department": "Solid Waste Management", "keywords": ["uncollected garbage", "garbage not collected", "waste not picked"], "base_severity": "MEDIUM", "validator_category": "garbage"},
    "Overflowing Bin": {"category": "Solid Waste", "department": "Solid Waste Management", "keywords": ["overflowing bin", "dustbin full", "bin overflow"], "base_severity": "MEDIUM", "validator_category": "waste"},
    "Illegal Dumping": {"category": "Solid Waste", "department": "Municipal Enforcement", "keywords": ["illegal dumping", "dumped waste", "dumping ground"], "base_severity": "MEDIUM", "validator_category": "illegal_dumping"},
    "Construction Debris": {"category": "Solid Waste", "department": "Solid Waste Management", "keywords": ["construction debris", "rubble", "construction waste"], "base_severity": "LOW", "validator_category": "waste"},

    # Street Lighting / Electrical
    "Broken Streetlight": {"category": "Street Lighting", "department": "Street Lighting / Electrical", "keywords": ["streetlight", "street light", "lamp post", "lamp not working"], "base_severity": "MEDIUM", "validator_category": "streetlight"},
    "Flickering Streetlight": {"category": "Street Lighting", "department": "Street Lighting / Electrical", "keywords": ["flickering", "flickering light", "flickering streetlight"], "base_severity": "LOW", "validator_category": "streetlight"},
    "Exposed Electrical Wire": {"category": "Street Lighting", "department": "Street Lighting / Electrical", "keywords": ["exposed wire", "live wire", "electrical wire", "loose wire"], "base_severity": "CRITICAL", "validator_category": "other"},
    "Damaged Electrical Pole": {"category": "Street Lighting", "department": "Street Lighting / Electrical", "keywords": ["damaged pole", "electric pole", "leaning pole", "broken pole"], "base_severity": "HIGH", "validator_category": "other"},

    # Drainage
    "Open Drain": {"category": "Drainage", "department": "Storm Water Drainage", "keywords": ["open drain", "uncovered drain"], "base_severity": "HIGH", "validator_category": "drainage"},
    "Blocked Drain": {"category": "Drainage", "department": "Storm Water Drainage", "keywords": ["blocked drain", "clogged drain"], "base_severity": "MEDIUM", "validator_category": "drainage"},
    "Overflowing Drain": {"category": "Drainage", "department": "Storm Water Drainage", "keywords": ["overflowing drain", "drain overflow"], "base_severity": "HIGH", "validator_category": "drainage"},
    "Waterlogging": {"category": "Drainage", "department": "Storm Water Drainage", "keywords": ["waterlogging", "water logging", "flooded street", "stagnant water"], "base_severity": "HIGH", "validator_category": "flooding"},

    # Sewerage
    "Sewage Overflow": {"category": "Sewerage", "department": "Sewerage", "keywords": ["sewage", "sewer overflow", "sewage overflow"], "base_severity": "CRITICAL", "validator_category": "sewage"},
    "Missing Manhole Cover": {"category": "Sewerage", "department": "Sewerage", "keywords": ["manhole cover missing", "no manhole cover", "open manhole"], "base_severity": "CRITICAL", "validator_category": "sewage"},
    "Damaged Manhole": {"category": "Sewerage", "department": "Sewerage", "keywords": ["damaged manhole", "broken manhole"], "base_severity": "HIGH", "validator_category": "sewage"},

    # Water
    "Water Leakage": {"category": "Water Supply", "department": "Water Supply", "keywords": ["water leak", "water leakage", "leaking pipe"], "base_severity": "MEDIUM", "validator_category": "water_leak"},
    "Broken Pipeline": {"category": "Water Supply", "department": "Water Supply", "keywords": ["broken pipeline", "pipeline burst", "burst pipe"], "base_severity": "HIGH", "validator_category": "water_leak"},
    "Water Supply Issue": {"category": "Water Supply", "department": "Water Supply", "keywords": ["no water supply", "water supply issue", "no water"], "base_severity": "MEDIUM", "validator_category": "water_leak"},

    # Footpath / Public Infrastructure
    "Damaged Footpath": {"category": "Public Infrastructure", "department": "Roads / Public Works", "keywords": ["footpath", "sidewalk", "pavement damage"], "base_severity": "LOW", "validator_category": "sidewalk"},
    "Broken Bench": {"category": "Public Infrastructure", "department": "Parks", "keywords": ["broken bench", "park bench", "damaged bench"], "base_severity": "LOW", "validator_category": "other"},
    "Damaged Sign": {"category": "Public Infrastructure", "department": "Traffic", "keywords": ["road sign", "damaged sign", "signboard"], "base_severity": "LOW", "validator_category": "other"},
    "Public Property Damage": {"category": "Public Infrastructure", "department": "General Civic Support", "keywords": ["public property damage", "vandalism"], "base_severity": "LOW", "validator_category": "other"},

    # Traffic
    "Traffic Signal Failure": {"category": "Traffic", "department": "Traffic", "keywords": ["traffic signal", "traffic light not working", "signal failure"], "base_severity": "HIGH", "validator_category": "traffic_signal"},
    "Illegal Parking": {"category": "Traffic", "department": "Traffic", "keywords": ["illegal parking", "parked illegally"], "base_severity": "LOW", "validator_category": "other"},
    "Abandoned Vehicle": {"category": "Traffic", "department": "Traffic", "keywords": ["abandoned vehicle", "abandoned car"], "base_severity": "LOW", "validator_category": "other"},

    # Environment
    "Fallen Tree": {"category": "Environment", "department": "Parks", "keywords": ["fallen tree", "tree fell", "tree blocking"], "base_severity": "CRITICAL", "validator_category": "fallen_tree"},
    "Dangerous Tree Branch": {"category": "Environment", "department": "Parks", "keywords": ["dangerous branch", "hanging branch", "tree branch"], "base_severity": "HIGH", "validator_category": "tree_damage"},
    "Park Damage": {"category": "Environment", "department": "Parks", "keywords": ["park damage", "damaged park"], "base_severity": "LOW", "validator_category": "other"},

    # Sanitation
    "Public Toilet Issue": {"category": "Sanitation", "department": "Public Health / Sanitation", "keywords": ["public toilet", "restroom", "toilet issue"], "base_severity": "MEDIUM", "validator_category": "public_toilet"},
    "Dead Animal": {"category": "Sanitation", "department": "Public Health / Sanitation", "keywords": ["dead animal", "animal carcass"], "base_severity": "HIGH", "validator_category": "other"},

    # Animal Issues
    "Stray Animal": {"category": "Animal Welfare", "department": "Animal Welfare / Veterinary", "keywords": ["stray dog", "stray animal", "stray cattle"], "base_severity": "MEDIUM", "validator_category": "stray_animal"},
    "Injured Animal": {"category": "Animal Welfare", "department": "Animal Welfare / Veterinary", "keywords": ["injured animal", "hurt animal"], "base_severity": "MEDIUM", "validator_category": "stray_animal"},

    # Civic Enforcement
    "Encroachment": {"category": "Civic Enforcement", "department": "Municipal Enforcement", "keywords": ["encroachment", "illegal construction", "encroached"], "base_severity": "MEDIUM", "validator_category": "other"},
    "Public Nuisance": {"category": "Civic Enforcement", "department": "Municipal Enforcement", "keywords": ["public nuisance", "nuisance"], "base_severity": "LOW", "validator_category": "noise"},

    "Other": {"category": "Other", "department": "General Civic Support", "keywords": [], "base_severity": "MEDIUM", "validator_category": "other"},
}

DEPARTMENTS = [
    ("Roads / Public Works", "ROADS"),
    ("Solid Waste Management", "WASTE"),
    ("Street Lighting / Electrical", "ELECTRICAL"),
    ("Storm Water Drainage", "DRAINAGE"),
    ("Sewerage", "SEWERAGE"),
    ("Water Supply", "WATER"),
    ("Traffic", "TRAFFIC"),
    ("Parks", "PARKS"),
    ("Public Health / Sanitation", "SANITATION"),
    ("Animal Welfare / Veterinary", "ANIMAL"),
    ("Municipal Enforcement", "ENFORCEMENT"),
    ("General Civic Support", "GENERAL"),
]

CRITICAL_CONTEXT_KEYWORDS = ["school", "hospital", "children", "kids playing"]


def classify_keywords(text: str):
    """Very simple deterministic keyword matcher used by the mock AI classifier."""
    text_lower = (text or "").lower()
    best_match = None
    best_score = 0
    for issue_type, cfg in ISSUE_TYPES.items():
        for kw in cfg["keywords"]:
            if kw in text_lower:
                score = len(kw)
                if score > best_score:
                    best_score = score
                    best_match = issue_type
    return best_match


def to_validator_category(issue_type: str) -> str:
    """Map an internal issue_type to the fixed category vocabulary that the
    canonical validator.py accepts. Always returns a supported slug — falls
    back to "other" (a valid validator.py category) for anything unmapped."""
    cfg = ISSUE_TYPES.get(issue_type)
    if not cfg:
        return "other"
    return cfg.get("validator_category", "other")
