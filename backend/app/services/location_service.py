"""
Geospatial helpers.

This module is purely deterministic (Haversine distance + nearest-POI
lookup). It feeds the `location_type` attribute that the canonical
app/services/core/priority.py uses for its own location scoring — it does
not compute a location score itself.
"""
import math
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.issue import PointOfInterest

# Maps our seeded POI types to the fixed location_type vocabulary that
# priority.py's LOCATION_SCORES understands.
POI_TYPE_TO_LOCATION_TYPE = {
    "school": "school",
    "hospital": "hospital",
    "bus_stop": "public_transport",
    "railway_station": "public_transport",
    "transport_hub": "public_transport",
    "market": "market",
    "main_road": "busy_road",
    "government_office": "critical_infrastructure",
}

POI_LABELS = {
    "school": "Government School",
    "hospital": "Hospital",
    "bus_stop": "Bus Stop",
    "railway_station": "Railway Station",
    "market": "Market",
    "government_office": "Government Office",
    "main_road": "Main Road",
    "transport_hub": "Transport Hub",
}

# A POI must be within this radius to influence location_type at all.
NEARBY_RADIUS_METERS = 300

DEFAULT_LOCATION_TYPE = "normal_area"


def haversine_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


@dataclass
class LocationInfo:
    location_type: str  # normalized value for priority.calculate_priority()
    location_context: str  # human-readable display string


def describe_location(db: Session, latitude: float, longitude: float) -> LocationInfo:
    """Find the nearest relevant point of interest and derive both the
    normalized location_type (for priority.py) and a human-readable
    location_context string (for the admin UI)."""
    pois = db.query(PointOfInterest).all()

    best_poi = None
    best_distance = None

    # "Importance" here just orders which nearby POI wins when several are
    # in range — schools/hospitals/critical infra outrank a nearby bus stop.
    priority_order = {"school": 4, "hospital": 4, "government_office": 3, "market": 2, "main_road": 2, "transport_hub": 1, "railway_station": 1, "bus_stop": 1}

    best_rank = -1
    for poi in pois:
        distance = haversine_meters(latitude, longitude, poi.latitude, poi.longitude)
        if distance <= NEARBY_RADIUS_METERS:
            rank = priority_order.get(poi.poi_type, 0)
            if rank > best_rank:
                best_rank = rank
                best_poi = poi
                best_distance = distance

    if best_poi:
        label = POI_LABELS.get(best_poi.poi_type, best_poi.poi_type)
        location_type = POI_TYPE_TO_LOCATION_TYPE.get(best_poi.poi_type, DEFAULT_LOCATION_TYPE)
        context = f"Near {best_poi.name} ({label}), {int(best_distance)}m away"
        return LocationInfo(location_type=location_type, location_context=context)

    return LocationInfo(location_type=DEFAULT_LOCATION_TYPE, location_context="No significant public landmark nearby")
