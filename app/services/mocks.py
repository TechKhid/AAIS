from __future__ import annotations

import math
from uuid import uuid4

from app.schemas import Hospital, Incident, NotificationEvent, PatientRecord, RouteEstimate
from app.store import InMemoryStore


class MockIntegrationService:
    def __init__(self, store: InMemoryStore) -> None:
        self.store = store

    def lookup_patient_record(self, incident: Incident) -> PatientRecord | None:
        patient = incident.patient
        return self.store.find_patient_record(patient.ghana_card_id, patient.nhis_id, patient.patient_id)

    def estimate_route(self, incident: Incident, hospital: Hospital) -> RouteEstimate:
        distance_km = _haversine_km(
            incident.scene_location.latitude,
            incident.scene_location.longitude,
            hospital.location.latitude,
            hospital.location.longitude,
        )
        traffic_level, factor = _traffic_for_city(hospital.city)
        minutes = max(4, round((distance_km / 38) * 60 * factor + _urban_delay_minutes(hospital.city)))
        return RouteEstimate(distance_km=round(distance_km, 1), eta_minutes=minutes, traffic_level=traffic_level)

    def send_prealert(self, incident: Incident, hospital: Hospital, summary: str) -> NotificationEvent:
        status = "sent" if hospital.contact_channel else "failed"
        return NotificationEvent(
            id=f"ntf-{uuid4().hex[:10]}",
            incident_id=incident.id,
            hospital_id=hospital.id,
            channel=hospital.contact_channel or "unconfigured",
            status=status,
            summary=summary,
        )

    def remote_triage_clinician(self, city: str) -> str:
        clinicians = {
            "Accra": "Dr. Nana Beyuo, National Emergency Command Centre",
            "Kumasi": "Dr. Akua Appiah, Ashanti EMS Desk",
            "Tamale": "Dr. Sulemana Fuseini, Northern EMS Desk",
        }
        return clinicians.get(city, "On-duty command centre clinician")


def _traffic_for_city(city: str) -> tuple[str, float]:
    traffic = {
        "Accra": ("heavy", 1.45),
        "Kumasi": ("moderate", 1.2),
        "Tamale": ("light", 1.0),
    }
    return traffic.get(city, ("moderate", 1.15))


def _urban_delay_minutes(city: str) -> int:
    return {"Accra": 7, "Kumasi": 5, "Tamale": 3}.get(city, 5)


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_km = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    )
    return 2 * radius_km * math.asin(math.sqrt(a))

