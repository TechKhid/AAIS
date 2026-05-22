from __future__ import annotations

from uuid import uuid4

from app.schemas import (
    Ambulance,
    HandoverSummary,
    HandoverRequest,
    Incident,
    IncidentCreate,
    Location,
    PatientSnapshot,
    SimulationScenario,
    SimulationSession,
    SimulationStep,
    SimulationStepResult,
    Vitals,
    utc_now,
)
from app.services.llm_client import LLMResponseError, LMStudioClient, LMStudioUnavailable
from app.services.mocks import MockIntegrationService
from app.services.routing import RoutingService
from app.store import InMemoryStore


SIMULATION_STEPS = [
    ("dispatch", "Dispatch and patient pickup"),
    ("ai_triage", "LLM-assisted triage"),
    ("routing", "Hospital recommendation"),
    ("destination", "Destination confirmation"),
    ("prealert", "Hospital pre-alert"),
    ("transport", "Ambulance transport update"),
    ("handover", "Digital handover"),
]


class SimulationEngine:
    def __init__(
        self,
        store: InMemoryStore,
        integrations: MockIntegrationService,
        routing_service: RoutingService,
        llm_client: LMStudioClient,
    ) -> None:
        self.store = store
        self.integrations = integrations
        self.routing_service = routing_service
        self.llm_client = llm_client

    def list_scenarios(self) -> list[SimulationScenario]:
        return list(_scenario_catalog().values())

    def get_scenario(self, scenario_id: str) -> SimulationScenario | None:
        return _scenario_catalog().get(scenario_id)

    def start(self, scenario_id: str) -> SimulationSession:
        scenario = self.get_scenario(scenario_id)
        if not scenario:
            raise KeyError(scenario_id)
        session = SimulationSession(
            id=f"sim-{uuid4().hex[:8]}",
            scenario_id=scenario.id,
            scenario_name=scenario.name,
            status="ready",
            steps=[SimulationStep(id=step_id, label=label) for step_id, label in SIMULATION_STEPS],
        )
        saved = self.store.save_simulation_session(session)
        self.store.record_event(
            event_type="simulation.started",
            actor="simulation-engine",
            message=f"Simulation started: {scenario.name}.",
            related_ids={"simulation_id": saved.id},
        )
        return saved

    async def step(self, session_id: str) -> SimulationStepResult:
        session = self._require_session(session_id)
        if session.status == "completed":
            return SimulationStepResult(session=session, incident=self._session_incident(session), message="Simulation already completed.")
        if session.status == "failed":
            return SimulationStepResult(session=session, incident=self._session_incident(session), message="Simulation is failed.")

        scenario = self.get_scenario(session.scenario_id)
        if not scenario:
            failed = self._fail(session, f"Scenario not found: {session.scenario_id}")
            return SimulationStepResult(session=failed, incident=self._session_incident(failed), message=failed.last_error or "Failed.")

        step_index = session.current_step_index
        if step_index >= len(session.steps):
            completed = self._complete(session, "Simulation completed.")
            return SimulationStepResult(session=completed, incident=self._session_incident(completed), message="Simulation completed.")

        current = session.steps[step_index]
        running = self._mark_step(session, step_index, status="running", summary=None)

        try:
            result = await self._execute_step(running, scenario, current.id)
        except LMStudioUnavailable as exc:
            paused = self._mark_step(running, step_index, status="paused", summary=str(exc))
            paused = self.store.save_simulation_session(paused.model_copy(update={"status": "paused", "last_error": f"LLM unavailable: {exc}"}))
            self.store.record_event(
                event_type="simulation.paused",
                actor="simulation-engine",
                message=paused.last_error or "Simulation paused.",
                related_ids={"simulation_id": paused.id, "incident_id": paused.incident_id or ""},
            )
            return SimulationStepResult(session=paused, incident=self._session_incident(paused), message=paused.last_error or "Paused.")
        except LLMResponseError as exc:
            paused = self._mark_step(running, step_index, status="paused", summary=str(exc))
            paused = self.store.save_simulation_session(paused.model_copy(update={"status": "paused", "last_error": str(exc)}))
            self.store.record_event(
                event_type="simulation.paused",
                actor="simulation-engine",
                message=str(exc),
                related_ids={"simulation_id": paused.id, "incident_id": paused.incident_id or ""},
            )
            return SimulationStepResult(session=paused, incident=self._session_incident(paused), message=str(exc))
        except Exception as exc:  # noqa: BLE001 - simulation should preserve session state for the UI.
            failed = self._fail(running, str(exc), step_index=step_index)
            return SimulationStepResult(session=failed, incident=self._session_incident(failed), message=failed.last_error or "Failed.")

        advanced = self._mark_step(result.session, step_index, status="complete", summary=result.message)
        next_index = step_index + 1
        status = "completed" if next_index >= len(advanced.steps) else "running"
        advanced = self.store.save_simulation_session(
            advanced.model_copy(
                update={
                    "status": status,
                    "current_step_index": next_index,
                    "last_error": None,
                }
            )
        )
        if status == "completed":
            self.store.record_event(
                event_type="simulation.completed",
                actor="simulation-engine",
                message=f"Simulation completed: {scenario.name}.",
                related_ids={"simulation_id": advanced.id, "incident_id": advanced.incident_id or ""},
            )
        return SimulationStepResult(session=advanced, incident=self._session_incident(advanced), message=result.message)

    async def run(self, session_id: str, max_steps: int = 10) -> SimulationStepResult:
        result: SimulationStepResult | None = None
        for _ in range(max_steps):
            result = await self.step(session_id)
            if result.session.status in {"paused", "completed", "failed"}:
                return result
        assert result is not None
        return result

    async def _execute_step(
        self,
        session: SimulationSession,
        scenario: SimulationScenario,
        step_id: str,
    ) -> SimulationStepResult:
        if step_id == "dispatch":
            incident = self.store.create_incident(
                IncidentCreate(
                    ambulance_id=scenario.ambulance_id,
                    scene_location=scenario.scene_location,
                    patient=scenario.patient,
                ),
                self.store.find_patient_record(
                    scenario.patient.ghana_card_id,
                    scenario.patient.nhis_id,
                    scenario.patient.patient_id,
                ),
            )
            session = self.store.save_simulation_session(session.model_copy(update={"incident_id": incident.id, "status": "running"}))
            return SimulationStepResult(session=session, incident=incident, message=f"Incident {incident.id} opened and assigned to {scenario.ambulance_id}.")

        incident = self._require_incident(session)

        if step_id == "ai_triage":
            triage = await self.llm_client.triage_incident(incident)
            incident = self.store.set_triage(incident.id, triage)
            clinician = self.integrations.remote_triage_clinician(incident.scene_location.city)
            self.store.record_event(
                event_type="remote_triage.reviewed",
                actor=clinician,
                message=f"{clinician} reviewed LLM triage for {incident.id}.",
                related_ids={"simulation_id": session.id, "incident_id": incident.id},
            )
            return SimulationStepResult(session=session, incident=incident, message=f"LLM triage completed: {triage.acuity} acuity, {', '.join(triage.care_pathways)}.")

        if step_id == "routing":
            recommendations = self.routing_service.rank_hospitals(incident)
            incident = self.store.set_recommendations(incident.id, recommendations)
            top = next((item for item in recommendations if not item.blocked), recommendations[0])
            return SimulationStepResult(session=session, incident=incident, message=f"Top recommendation: {top.hospital_name} with score {top.score}.")

        if step_id == "destination":
            top = next((item for item in incident.recommendations if not item.blocked), None)
            if not top:
                raise RuntimeError("No unblocked hospital recommendation is available.")
            incident = self.store.set_destination(incident.id, top.hospital_id)
            session = self.store.save_simulation_session(session.model_copy(update={"selected_hospital_id": top.hospital_id}))
            return SimulationStepResult(session=session, incident=incident, message=f"Destination confirmed: {top.hospital_name}.")

        if step_id == "prealert":
            if not incident.selected_hospital_id:
                raise RuntimeError("Destination must be confirmed before pre-alert.")
            summary = await self.llm_client.generate_prealert(incident)
            hospital = self.store.hospitals[incident.selected_hospital_id]
            notification = self.integrations.send_prealert(incident, hospital, summary)
            incident = self.store.set_notification(incident.id, notification)
            return SimulationStepResult(session=session, incident=incident, message=f"Pre-alert sent to {hospital.name}.")

        if step_id == "transport":
            if not incident.selected_hospital_id:
                raise RuntimeError("Destination must be confirmed before transport.")
            hospital = self.store.hospitals[incident.selected_hospital_id]
            ambulance = self.store.ambulances[incident.ambulance_id]
            updated = _move_ambulance_towards_hospital(ambulance, hospital.location, incident.id)
            self.store.update_ambulance(updated)
            incident = self.store.save_incident(incident.model_copy(update={"status": "en_route"}))
            self.store.record_event(
                event_type="simulation.transport_progress",
                actor=ambulance.id,
                message=f"{ambulance.call_sign} is en route to {hospital.name}.",
                related_ids={"simulation_id": session.id, "incident_id": incident.id, "hospital_id": hospital.id},
            )
            return SimulationStepResult(session=session, incident=incident, message=f"Ambulance en route to {hospital.name}.")

        if step_id == "handover":
            if not incident.selected_hospital_id:
                raise RuntimeError("Destination must be confirmed before handover.")
            final_vitals = scenario.patient.vitals
            summary = await self.llm_client.generate_handover(
                incident,
                HandoverRequest(
                    treatments_administered=scenario.handover_treatments,
                    observations=scenario.handover_observations,
                    final_vitals=final_vitals,
                ),
            )
            incident = self.store.set_handover(
                incident.id,
                HandoverSummary(
                    incident_id=incident.id,
                    hospital_id=incident.selected_hospital_id,
                    summary=summary,
                ),
            )
            return SimulationStepResult(session=session, incident=incident, message="Digital handover completed.")

        raise RuntimeError(f"Unknown simulation step: {step_id}")

    def _require_session(self, session_id: str) -> SimulationSession:
        session = self.store.get_simulation_session(session_id)
        if not session:
            raise KeyError(session_id)
        return session

    def _require_incident(self, session: SimulationSession) -> Incident:
        incident = self._session_incident(session)
        if not incident:
            raise RuntimeError("Simulation has no incident yet.")
        return incident

    def _session_incident(self, session: SimulationSession) -> Incident | None:
        if not session.incident_id:
            return None
        return self.store.get_incident(session.incident_id)

    def _mark_step(
        self,
        session: SimulationSession,
        step_index: int,
        status: str,
        summary: str | None,
    ) -> SimulationSession:
        steps = list(session.steps)
        steps[step_index] = steps[step_index].model_copy(
            update={
                "status": status,
                "summary": summary,
                "completed_at": utc_now() if status == "complete" else steps[step_index].completed_at,
            }
        )
        return self.store.save_simulation_session(session.model_copy(update={"steps": steps, "status": "running"}))

    def _fail(self, session: SimulationSession, error: str, step_index: int | None = None) -> SimulationSession:
        if step_index is not None:
            session = self._mark_step(session, step_index, status="failed", summary=error)
        failed = self.store.save_simulation_session(session.model_copy(update={"status": "failed", "last_error": error}))
        self.store.record_event(
            event_type="simulation.failed",
            actor="simulation-engine",
            message=error,
            related_ids={"simulation_id": failed.id, "incident_id": failed.incident_id or ""},
        )
        return failed

    def _complete(self, session: SimulationSession, message: str) -> SimulationSession:
        return self.store.save_simulation_session(session.model_copy(update={"status": "completed", "last_error": None}))


def _move_ambulance_towards_hospital(ambulance: Ambulance, hospital_location: Location, incident_id: str) -> Ambulance:
    latitude = ambulance.location.latitude + ((hospital_location.latitude - ambulance.location.latitude) * 0.72)
    longitude = ambulance.location.longitude + ((hospital_location.longitude - ambulance.location.longitude) * 0.72)
    return ambulance.model_copy(
        update={
            "status": "en_route",
            "current_incident_id": incident_id,
            "location": Location(
                city=hospital_location.city,
                latitude=round(latitude, 5),
                longitude=round(longitude, 5),
                address=f"En route toward {hospital_location.address or hospital_location.city}",
            ),
        }
    )


def _scenario_catalog() -> dict[str, SimulationScenario]:
    scenarios = [
        SimulationScenario(
            id="accra-stroke",
            name="Accra suspected stroke",
            city="Accra",
            pathway="stroke",
            acuity_hint="red",
            description="Time-sensitive stroke pathway with CT and ICU capability requirements.",
            ambulance_id="amb-accra-01",
            scene_location=Location(city="Accra", latitude=5.5792, longitude=-0.2057, address="Osu Oxford Street"),
            patient=PatientSnapshot(
                name="Kwame Owusu",
                ghana_card_id="GHA-222333444-1",
                nhis_id="NHIS-AC-0002",
                age=61,
                sex="male",
                chief_complaint="Sudden right-sided weakness, facial droop, and slurred speech started 35 minutes ago.",
                notes="Known atrial fibrillation. Family reports he is normally independent.",
                vitals=Vitals(heart_rate=112, systolic_bp=178, diastolic_bp=96, respiratory_rate=20, oxygen_saturation=94, temperature_c=36.9, gcs=14, pain_score=0),
            ),
            expected_capabilities=["ct", "icu", "oxygen", "neurologist"],
            handover_treatments=["oxygen applied", "IV access established", "continuous cardiac monitoring"],
            handover_observations="Neurologic deficit persisted during transport without airway compromise.",
        ),
        SimulationScenario(
            id="accra-trauma",
            name="Accra road trauma",
            city="Accra",
            pathway="trauma",
            acuity_hint="red",
            description="Major trauma with head injury, hypotension, CT, surgical, blood bank, and ICU needs.",
            ambulance_id="amb-accra-01",
            scene_location=Location(city="Accra", latitude=5.6037, longitude=-0.1870, address="Airport bypass collision scene"),
            patient=PatientSnapshot(
                age=29,
                sex="male",
                chief_complaint="Motorbike crash with head injury, brief loss of consciousness, and deep thigh bleeding.",
                notes="Helmet cracked. Active bleeding controlled with pressure dressing.",
                vitals=Vitals(heart_rate=132, systolic_bp=88, diastolic_bp=54, respiratory_rate=26, oxygen_saturation=91, temperature_c=36.1, gcs=10, pain_score=8),
            ),
            expected_capabilities=["ct", "icu", "surgical_team", "blood_bank", "neurosurgeon"],
            handover_treatments=["pressure dressing", "oxygen applied", "two IV lines established", "spinal precautions"],
            handover_observations="Patient remained hypotensive with altered mental status.",
        ),
        SimulationScenario(
            id="accra-obstetric",
            name="Accra obstetric emergency",
            city="Accra",
            pathway="obstetric",
            acuity_hint="red",
            description="Late-pregnancy bleeding requiring obstetric, neonatal, blood bank, and theatre readiness.",
            ambulance_id="amb-accra-02",
            scene_location=Location(city="Accra", latitude=5.5486, longitude=-0.2012, address="Jamestown clinic transfer"),
            patient=PatientSnapshot(
                name="Ama Serwaa",
                ghana_card_id="GHA-123456789-0",
                nhis_id="NHIS-AC-0001",
                age=34,
                sex="female",
                chief_complaint="Thirty-six weeks pregnant with heavy vaginal bleeding and dizziness.",
                notes="Possible placental abruption. Midwife requests urgent obstetric receiving unit.",
                vitals=Vitals(heart_rate=124, systolic_bp=92, diastolic_bp=58, respiratory_rate=24, oxygen_saturation=96, temperature_c=36.8, gcs=15, pain_score=7),
            ),
            expected_capabilities=["maternity", "neonatal_support", "blood_bank", "obstetrician"],
            handover_treatments=["left lateral positioning", "oxygen applied", "IV fluids started"],
            handover_observations="Ongoing bleeding reported by referring midwife.",
        ),
        SimulationScenario(
            id="kumasi-cardiac",
            name="Kumasi chest pain",
            city="Kumasi",
            pathway="cardiac",
            acuity_hint="orange",
            description="Chest pain case balancing cardiology coverage, ER load, and travel time.",
            ambulance_id="amb-kumasi-01",
            scene_location=Location(city="Kumasi", latitude=6.6666, longitude=-1.6163, address="Adum market area"),
            patient=PatientSnapshot(
                age=54,
                sex="female",
                chief_complaint="Crushing central chest pain with sweating and nausea for 40 minutes.",
                notes="Pain radiates to left arm. No known allergies.",
                vitals=Vitals(heart_rate=104, systolic_bp=150, diastolic_bp=88, respiratory_rate=22, oxygen_saturation=95, temperature_c=36.7, gcs=15, pain_score=9),
            ),
            expected_capabilities=["oxygen", "icu", "cardiologist"],
            handover_treatments=["aspirin given", "oxygen available", "cardiac monitoring"],
            handover_observations="Chest pain persisted but patient remained alert.",
        ),
        SimulationScenario(
            id="tamale-pediatric-respiratory",
            name="Tamale pediatric respiratory distress",
            city="Tamale",
            pathway="pediatric respiratory",
            acuity_hint="orange",
            description="Child with severe asthma symptoms needing pediatric oxygen-capable receiving unit.",
            ambulance_id="amb-tamale-01",
            scene_location=Location(city="Tamale", latitude=9.4125, longitude=-0.8529, address="Lamashegu"),
            patient=PatientSnapshot(
                name="Amina Yakubu",
                ghana_card_id="GHA-777888999-2",
                nhis_id="NHIS-TM-0007",
                age=7,
                sex="female",
                chief_complaint="Severe wheezing, chest tightness, and exhaustion after asthma symptoms all night.",
                notes="Home inhaler no longer helping.",
                vitals=Vitals(heart_rate=138, systolic_bp=100, diastolic_bp=66, respiratory_rate=36, oxygen_saturation=88, temperature_c=37.4, gcs=15, pain_score=4),
            ),
            expected_capabilities=["oxygen", "pediatric", "pediatrician"],
            handover_treatments=["oxygen applied", "nebulized bronchodilator started", "continuous monitoring"],
            handover_observations="Work of breathing remained high during transport.",
        ),
    ]
    return {scenario.id: scenario for scenario in scenarios}
