from __future__ import annotations

from threading import RLock
from uuid import uuid4

from app.schemas import (
    Ambulance,
    CapacityStatus,
    EventRecord,
    HandoverSummary,
    Hospital,
    HospitalRecommendation,
    Incident,
    IncidentCreate,
    NotificationEvent,
    PatientRecord,
    SimulationSession,
    TriageSignal,
    utc_now,
)
from app.seed_data import patient_identifier_index, seed_ambulances, seed_hospitals, seed_patient_records


class InMemoryStore:
    def __init__(self) -> None:
        self._lock = RLock()
        self.reset()

    def reset(self) -> None:
        with self._lock:
            self.hospitals: dict[str, Hospital] = seed_hospitals()
            self.ambulances: dict[str, Ambulance] = seed_ambulances()
            self.patient_records: dict[str, PatientRecord] = seed_patient_records()
            self.patient_identifier_index: dict[str, str] = patient_identifier_index()
            self.incidents: dict[str, Incident] = {}
            self.simulation_sessions: dict[str, SimulationSession] = {}
            self.events: list[EventRecord] = []
            self.record_event(
                event_type="system.boot",
                actor="system",
                message="AAIS mock command center initialized with Ghana pilot fixtures.",
            )

    def record_event(
        self,
        event_type: str,
        actor: str,
        message: str,
        related_ids: dict[str, str] | None = None,
        payload: dict | None = None,
    ) -> EventRecord:
        event = EventRecord(
            id=f"evt-{uuid4().hex[:10]}",
            event_type=event_type,
            actor=actor,
            message=message,
            related_ids=related_ids or {},
            payload=payload or {},
        )
        self.events.append(event)
        return event

    def list_events(self, limit: int = 100) -> list[EventRecord]:
        return list(reversed(self.events[-limit:]))

    def create_incident(self, payload: IncidentCreate, patient_record: PatientRecord | None) -> Incident:
        with self._lock:
            incident = Incident(
                id=f"inc-{uuid4().hex[:8]}",
                ambulance_id=payload.ambulance_id,
                scene_location=payload.scene_location,
                patient=payload.patient,
                patient_record=patient_record,
            )
            self.incidents[incident.id] = incident
            ambulance = self.ambulances[payload.ambulance_id]
            self.ambulances[payload.ambulance_id] = ambulance.model_copy(
                update={
                    "status": "assigned",
                    "current_incident_id": incident.id,
                    "updated_at": utc_now(),
                }
            )
            self.record_event(
                event_type="incident.created",
                actor=payload.ambulance_id,
                message=f"Incident {incident.id} created from {payload.scene_location.city}.",
                related_ids={"incident_id": incident.id, "ambulance_id": payload.ambulance_id},
            )
            return incident

    def get_incident(self, incident_id: str) -> Incident | None:
        return self.incidents.get(incident_id)

    def save_incident(self, incident: Incident) -> Incident:
        with self._lock:
            updated = incident.model_copy(update={"updated_at": utc_now()})
            self.incidents[updated.id] = updated
            return updated

    def find_patient_record(self, ghana_card_id: str | None, nhis_id: str | None, patient_id: str | None) -> PatientRecord | None:
        identifiers = [value for value in [patient_id, ghana_card_id, nhis_id] if value]
        for identifier in identifiers:
            indexed_id = self.patient_identifier_index.get(identifier, identifier)
            if indexed_id in self.patient_records:
                return self.patient_records[indexed_id]
        return None

    def update_capacity(self, hospital_id: str, capacity: CapacityStatus) -> Hospital | None:
        with self._lock:
            hospital = self.hospitals.get(hospital_id)
            if not hospital:
                return None
            updated = hospital.model_copy(update={"capacity": capacity.model_copy(update={"updated_at": utc_now()})})
            self.hospitals[hospital_id] = updated
            self.record_event(
                event_type="hospital.capacity_updated",
                actor=hospital_id,
                message=f"{hospital.name} capacity updated.",
                related_ids={"hospital_id": hospital_id},
            )
            return updated

    def update_ambulance(self, ambulance: Ambulance) -> Ambulance:
        with self._lock:
            updated = ambulance.model_copy(update={"updated_at": utc_now()})
            self.ambulances[ambulance.id] = updated
            return updated

    def set_triage(self, incident_id: str, triage: TriageSignal) -> Incident:
        incident = self.incidents[incident_id]
        updated = incident.model_copy(update={"triage_signal": triage, "status": "triaged"})
        saved = self.save_incident(updated)
        self.record_event(
            event_type="incident.ai_triaged",
            actor="lmstudio",
            message=f"LLM triage completed for {incident_id}: {triage.acuity}.",
            related_ids={"incident_id": incident_id},
            payload={"care_pathways": triage.care_pathways, "required_capabilities": triage.required_capabilities},
        )
        return saved

    def set_recommendations(self, incident_id: str, recommendations: list[HospitalRecommendation]) -> Incident:
        incident = self.incidents[incident_id]
        updated = incident.model_copy(update={"recommendations": recommendations, "status": "recommended"})
        saved = self.save_incident(updated)
        top = next((rec for rec in recommendations if not rec.blocked), recommendations[0] if recommendations else None)
        self.record_event(
            event_type="incident.recommendations_ready",
            actor="routing-engine",
            message=f"Routing recommendations ready for {incident_id}."
            + (f" Top candidate: {top.hospital_name}." if top else ""),
            related_ids={"incident_id": incident_id},
        )
        return saved

    def set_destination(self, incident_id: str, hospital_id: str) -> Incident:
        incident = self.incidents[incident_id]
        updated = incident.model_copy(update={"selected_hospital_id": hospital_id, "status": "destination_confirmed"})
        saved = self.save_incident(updated)
        ambulance = self.ambulances[incident.ambulance_id]
        self.update_ambulance(ambulance.model_copy(update={"status": "en_route"}))
        self.record_event(
            event_type="incident.destination_confirmed",
            actor=incident.ambulance_id,
            message=f"Destination confirmed for {incident_id}: {self.hospitals[hospital_id].name}.",
            related_ids={"incident_id": incident_id, "hospital_id": hospital_id},
        )
        return saved

    def set_notification(self, incident_id: str, notification: NotificationEvent) -> Incident:
        incident = self.incidents[incident_id]
        updated = incident.model_copy(update={"notification": notification, "status": "notified"})
        saved = self.save_incident(updated)
        self.record_event(
            event_type="hospital.prealert_sent",
            actor="notification-gateway",
            message=f"Pre-alert sent to {self.hospitals[notification.hospital_id].name}.",
            related_ids={"incident_id": incident_id, "hospital_id": notification.hospital_id},
        )
        return saved

    def set_handover(self, incident_id: str, handover: HandoverSummary) -> Incident:
        incident = self.incidents[incident_id]
        updated = incident.model_copy(update={"handover": handover, "status": "handover_complete"})
        saved = self.save_incident(updated)
        ambulance = self.ambulances[incident.ambulance_id]
        self.update_ambulance(ambulance.model_copy(update={"status": "at_hospital"}))
        self.record_event(
            event_type="incident.handover_complete",
            actor=incident.ambulance_id,
            message=f"Digital handover completed for {incident_id}.",
            related_ids={"incident_id": incident_id, "hospital_id": handover.hospital_id},
        )
        return saved

    def save_simulation_session(self, session: SimulationSession) -> SimulationSession:
        with self._lock:
            updated = session.model_copy(update={"updated_at": utc_now()})
            self.simulation_sessions[updated.id] = updated
            return updated

    def get_simulation_session(self, session_id: str) -> SimulationSession | None:
        return self.simulation_sessions.get(session_id)

    def list_simulation_sessions(self) -> list[SimulationSession]:
        return sorted(self.simulation_sessions.values(), key=lambda item: item.started_at, reverse=True)
