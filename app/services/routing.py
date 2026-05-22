from __future__ import annotations

from app.schemas import Hospital, HospitalRecommendation, Incident, RecommendationBreakdown
from app.services.mocks import MockIntegrationService
from app.store import InMemoryStore


ROUTING_WEIGHTS = {
    "clinical_fit": 40.0,
    "capacity_resources": 25.0,
    "eta": 20.0,
    "er_load": 10.0,
    "continuity": 5.0,
}

CRITICAL_CAPABILITIES = {"icu", "oxygen", "ct", "surgical_team", "neonatal_support", "ventilator"}


class RoutingService:
    def __init__(self, store: InMemoryStore, integrations: MockIntegrationService) -> None:
        self.store = store
        self.integrations = integrations

    def rank_hospitals(self, incident: Incident) -> list[HospitalRecommendation]:
        if not incident.triage_signal:
            raise ValueError("AI triage is required before routing.")

        region = _normalize_region(incident.scene_location.city)
        regional_hospitals = [
            hospital
            for hospital in self.store.hospitals.values()
            if _normalize_region(hospital.city) == region
        ]
        recommendations = [
            self._score_hospital(incident=incident, hospital=hospital)
            for hospital in regional_hospitals
        ]
        return sorted(recommendations, key=lambda item: (item.blocked, -item.score, item.route.eta_minutes))

    def _score_hospital(self, incident: Incident, hospital: Hospital) -> HospitalRecommendation:
        triage = incident.triage_signal
        required_capabilities = {_normalize(value) for value in triage.required_capabilities}
        required_specialists = {_normalize(value) for value in triage.required_specialists}
        available = _available_requirements(hospital)
        required = required_capabilities | required_specialists

        matched = sorted(required & available)
        missing = sorted(required - available)
        missing_critical = sorted((required_capabilities & CRITICAL_CAPABILITIES) - available)
        blocked = bool(missing_critical)

        clinical_score = len(matched) / len(required) if required else 1.0
        capacity_score = _capacity_score(hospital, required_capabilities)
        route = self.integrations.estimate_route(incident, hospital)
        eta_score = max(0.0, min(1.0, 1 - ((route.eta_minutes - 5) / 45)))
        load_score = max(0.0, 1 - hospital.capacity.er_load)
        continuity_score = _continuity_score(incident, hospital)

        breakdown = RecommendationBreakdown(
            clinical_fit=round(clinical_score * ROUTING_WEIGHTS["clinical_fit"], 2),
            capacity_resources=round(capacity_score * ROUTING_WEIGHTS["capacity_resources"], 2),
            eta=round(eta_score * ROUTING_WEIGHTS["eta"], 2),
            er_load=round(load_score * ROUTING_WEIGHTS["er_load"], 2),
            continuity=round(continuity_score * ROUTING_WEIGHTS["continuity"], 2),
            total=0,
        )
        total = 0.0 if blocked else sum(
            [
                breakdown.clinical_fit,
                breakdown.capacity_resources,
                breakdown.eta,
                breakdown.er_load,
                breakdown.continuity,
            ]
        )
        breakdown = breakdown.model_copy(update={"total": round(total, 2)})

        reasons = _build_reasons(
            hospital=hospital,
            matched=matched,
            missing=missing,
            missing_critical=missing_critical,
            route_minutes=route.eta_minutes,
            continuity_score=continuity_score,
        )
        return HospitalRecommendation(
            hospital_id=hospital.id,
            hospital_name=hospital.name,
            city=hospital.city,
            blocked=blocked,
            score=breakdown.total,
            breakdown=breakdown,
            route=route,
            matched_requirements=matched,
            missing_requirements=missing,
            reasons=reasons,
        )


def _available_requirements(hospital: Hospital) -> set[str]:
    available = {_normalize(item) for item in hospital.capabilities}
    capacity = hospital.capacity
    roster = hospital.specialists

    if capacity.er_beds_available > 0:
        available.add("er_bed")
    if capacity.icu_beds_available > 0:
        available.add("icu")
    if capacity.maternity_beds_available > 0:
        available.add("maternity")
    if capacity.pediatric_beds_available > 0:
        available.add("pediatric")
    if capacity.isolation_rooms_available > 0:
        available.add("isolation")
    if capacity.oxygen_points_available > 0:
        available.add("oxygen")
    if capacity.ventilators_available > 0:
        available.add("ventilator")
    if capacity.ct_available:
        available.add("ct")
    if capacity.surgical_team_available:
        available.add("surgical_team")
    if capacity.neonatal_support_available:
        available.add("neonatal_support")
    if capacity.blood_bank_available:
        available.add("blood_bank")

    specialist_counts = {
        "emergency_physician": roster.emergency_physicians,
        "surgeon": roster.surgeons,
        "neurosurgeon": roster.neurosurgeons,
        "neurologist": roster.neurologists,
        "obstetrician": roster.obstetricians,
        "pediatrician": roster.pediatricians,
        "cardiologist": roster.cardiologists,
        "anesthetist": roster.anesthetists,
    }
    available.update(name for name, count in specialist_counts.items() if count > 0)
    return available


def _capacity_score(hospital: Hospital, required_capabilities: set[str]) -> float:
    capacity = hospital.capacity
    bed_score = min(1.0, capacity.er_beds_available / 5)
    if "icu" in required_capabilities:
        bed_score = min(1.0, capacity.icu_beds_available / 2)
    elif "maternity" in required_capabilities or "neonatal_support" in required_capabilities:
        bed_score = min(1.0, capacity.maternity_beds_available / 3)
    elif "pediatric" in required_capabilities:
        bed_score = min(1.0, capacity.pediatric_beds_available / 3)

    equipment_checks = [
        capacity.oxygen_points_available > 0,
        capacity.monitors_available > 0,
        capacity.ventilators_available > 0 if "ventilator" in required_capabilities or "icu" in required_capabilities else True,
        capacity.ct_available if "ct" in required_capabilities else True,
        capacity.surgical_team_available if "surgical_team" in required_capabilities else True,
        capacity.neonatal_support_available if "neonatal_support" in required_capabilities else True,
        capacity.blood_bank_available if "blood_bank" in required_capabilities else True,
    ]
    equipment_score = sum(1 for item in equipment_checks if item) / len(equipment_checks)
    load_modifier = max(0.25, 1 - (capacity.er_load * 0.35))
    return max(0.0, min(1.0, ((bed_score * 0.55) + (equipment_score * 0.45)) * load_modifier))


def _continuity_score(incident: Incident, hospital: Hospital) -> float:
    if not incident.patient_record:
        return 0.4
    if hospital.id in incident.patient_record.preferred_hospitals:
        return 1.0
    return 0.2


def _build_reasons(
    hospital: Hospital,
    matched: list[str],
    missing: list[str],
    missing_critical: list[str],
    route_minutes: int,
    continuity_score: float,
) -> list[str]:
    reasons: list[str] = []
    if missing_critical:
        reasons.append(f"Blocked because critical capability is missing: {', '.join(missing_critical)}.")
    if matched:
        reasons.append(f"Matches {len(matched)} routing needs: {', '.join(matched[:5])}.")
    if missing and not missing_critical:
        reasons.append(f"Penalized for missing non-critical needs: {', '.join(missing[:5])}.")
    reasons.append(f"Estimated ambulance ETA is {route_minutes} minutes.")
    reasons.append(f"Current ER load is {round(hospital.capacity.er_load * 100)}%.")
    if continuity_score == 1.0:
        reasons.append("Patient record continuity favors this facility.")
    return reasons


def _normalize(value: str) -> str:
    return value.strip().lower().replace("-", "_").replace(" ", "_")


def _normalize_region(value: str) -> str:
    return value.strip().casefold()
