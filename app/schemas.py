from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class Location(ApiModel):
    city: str
    latitude: float
    longitude: float
    address: str | None = None


class Vitals(ApiModel):
    heart_rate: int | None = Field(default=None, ge=0)
    systolic_bp: int | None = Field(default=None, ge=0)
    diastolic_bp: int | None = Field(default=None, ge=0)
    respiratory_rate: int | None = Field(default=None, ge=0)
    oxygen_saturation: int | None = Field(default=None, ge=0, le=100)
    temperature_c: float | None = None
    gcs: int | None = Field(default=None, ge=3, le=15)
    pain_score: int | None = Field(default=None, ge=0, le=10)


class PatientSnapshot(ApiModel):
    name: str | None = None
    patient_id: str | None = None
    ghana_card_id: str | None = None
    nhis_id: str | None = None
    age: int = Field(ge=0, le=130)
    sex: Literal["female", "male", "unknown"]
    chief_complaint: str
    notes: str | None = None
    vitals: Vitals


class PatientRecord(ApiModel):
    patient_id: str
    name: str
    age: int
    sex: Literal["female", "male", "unknown"]
    allergies: list[str] = Field(default_factory=list)
    conditions: list[str] = Field(default_factory=list)
    medications: list[str] = Field(default_factory=list)
    preferred_hospitals: list[str] = Field(default_factory=list)
    fhir_reference: str


class IncidentCreate(ApiModel):
    ambulance_id: str
    scene_location: Location
    patient: PatientSnapshot


class CapacityStatus(ApiModel):
    er_beds_available: int = Field(ge=0)
    icu_beds_available: int = Field(ge=0)
    maternity_beds_available: int = Field(ge=0)
    pediatric_beds_available: int = Field(ge=0)
    isolation_rooms_available: int = Field(ge=0)
    oxygen_points_available: int = Field(ge=0)
    ventilators_available: int = Field(ge=0)
    monitors_available: int = Field(ge=0)
    ct_available: bool
    surgical_team_available: bool
    neonatal_support_available: bool
    blood_bank_available: bool
    er_load: float = Field(ge=0, le=1)
    updated_at: datetime = Field(default_factory=utc_now)


class SpecialistRoster(ApiModel):
    emergency_physicians: int = Field(ge=0)
    surgeons: int = Field(ge=0)
    neurosurgeons: int = Field(ge=0)
    neurologists: int = Field(ge=0)
    obstetricians: int = Field(ge=0)
    pediatricians: int = Field(ge=0)
    cardiologists: int = Field(ge=0)
    anesthetists: int = Field(ge=0)
    nurses: int = Field(ge=0)
    updated_at: datetime = Field(default_factory=utc_now)


class Hospital(ApiModel):
    id: str
    name: str
    city: str
    level: str
    location: Location
    capabilities: list[str]
    capacity: CapacityStatus
    specialists: SpecialistRoster
    contact_channel: str
    bed_barcodes: list[str] = Field(default_factory=list)


class Ambulance(ApiModel):
    id: str
    call_sign: str
    city: str
    status: Literal["available", "assigned", "en_route", "at_hospital", "offline"]
    location: Location
    crew: list[str]
    equipment: list[str]
    current_incident_id: str | None = None
    updated_at: datetime = Field(default_factory=utc_now)


class AmbulanceLocationUpdate(ApiModel):
    status: Literal["available", "assigned", "en_route", "at_hospital", "offline"] | None = None
    location: Location | None = None


class TriageSignal(ApiModel):
    acuity: Literal["red", "orange", "yellow", "green"]
    care_pathways: list[str]
    required_capabilities: list[str]
    required_specialists: list[str]
    summary: str
    rationale: str
    confidence: float = Field(ge=0, le=1)
    source_model: str


class RouteEstimate(ApiModel):
    distance_km: float
    eta_minutes: int
    traffic_level: Literal["light", "moderate", "heavy"]
    provider: str = "mock-traffic-provider"


class RecommendationBreakdown(ApiModel):
    clinical_fit: float
    capacity_resources: float
    eta: float
    er_load: float
    continuity: float
    total: float


class HospitalRecommendation(ApiModel):
    hospital_id: str
    hospital_name: str
    city: str
    blocked: bool
    score: float
    breakdown: RecommendationBreakdown
    route: RouteEstimate
    matched_requirements: list[str]
    missing_requirements: list[str]
    reasons: list[str]


class DestinationSelection(ApiModel):
    hospital_id: str


class NotificationEvent(ApiModel):
    id: str
    incident_id: str
    hospital_id: str
    channel: str
    status: Literal["sent", "failed"]
    summary: str
    sent_at: datetime = Field(default_factory=utc_now)


class HandoverRequest(ApiModel):
    treatments_administered: list[str] = Field(default_factory=list)
    observations: str | None = None
    final_vitals: Vitals | None = None


class HandoverSummary(ApiModel):
    incident_id: str
    hospital_id: str
    summary: str
    generated_at: datetime = Field(default_factory=utc_now)


class EventRecord(ApiModel):
    id: str
    timestamp: datetime = Field(default_factory=utc_now)
    event_type: str
    actor: str
    message: str
    related_ids: dict[str, str] = Field(default_factory=dict)
    payload: dict[str, Any] = Field(default_factory=dict)


class Incident(ApiModel):
    id: str
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    ambulance_id: str
    scene_location: Location
    patient: PatientSnapshot
    patient_record: PatientRecord | None = None
    status: Literal[
        "created",
        "triaged",
        "recommended",
        "destination_confirmed",
        "notified",
        "en_route",
        "handover_complete",
    ] = "created"
    triage_signal: TriageSignal | None = None
    recommendations: list[HospitalRecommendation] = Field(default_factory=list)
    selected_hospital_id: str | None = None
    notification: NotificationEvent | None = None
    handover: HandoverSummary | None = None


class RecommendationResponse(ApiModel):
    incident_id: str
    weights: dict[str, float]
    recommendations: list[HospitalRecommendation]


class HealthResponse(ApiModel):
    app: str
    status: Literal["ok"]
    lmstudio_available: bool
    lmstudio_base_url: str
    lmstudio_model: str
    lmstudio_resolved_model: str | None = None
    lmstudio_models: list[str] = Field(default_factory=list)
    detail: str | None = None


class CommandOverview(ApiModel):
    active_incidents: list[Incident]
    ambulances: list[Ambulance]
    hospitals: list[Hospital]
    recent_events: list[EventRecord]


class SimulationScenario(ApiModel):
    id: str
    name: str
    city: str
    pathway: str
    acuity_hint: Literal["red", "orange", "yellow", "green"]
    description: str
    ambulance_id: str
    scene_location: Location
    patient: PatientSnapshot
    expected_capabilities: list[str]
    handover_treatments: list[str] = Field(default_factory=list)
    handover_observations: str | None = None


class SimulationStep(ApiModel):
    id: str
    label: str
    status: Literal["pending", "running", "complete", "paused", "failed"] = "pending"
    summary: str | None = None
    completed_at: datetime | None = None


class SimulationSession(ApiModel):
    id: str
    scenario_id: str
    scenario_name: str
    status: Literal["ready", "running", "paused", "completed", "failed"] = "ready"
    current_step_index: int = 0
    incident_id: str | None = None
    selected_hospital_id: str | None = None
    started_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    last_error: str | None = None
    steps: list[SimulationStep]


class SimulationStartRequest(ApiModel):
    scenario_id: str


class SimulationStepResult(ApiModel):
    session: SimulationSession
    incident: Incident | None = None
    message: str
