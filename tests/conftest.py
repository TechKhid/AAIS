from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.schemas import HandoverRequest, Incident, TriageSignal
from app.services.llm_client import LMStudioUnavailable


class FakeLLM:
    async def health(self) -> dict:
        return {
            "available": True,
            "models": ["qwen/qwen3.5-9b"],
            "detail": None,
        }

    async def triage_incident(self, incident: Incident) -> TriageSignal:
        text = incident.patient.chief_complaint.lower()
        if "pregnant" in text or "vaginal bleeding" in text:
            return TriageSignal(
                acuity="red",
                care_pathways=["obstetric"],
                required_capabilities=["oxygen", "maternity", "neonatal_support", "blood_bank"],
                required_specialists=["obstetrician", "anesthetist"],
                summary="High-risk obstetric bleeding requiring urgent receiving unit.",
                rationale="Late pregnancy bleeding with tachycardia and low blood pressure.",
                confidence=0.91,
                source_model="fake-test-model",
            )
        if "wheezing" in text or "asthma" in text:
            return TriageSignal(
                acuity="orange",
                care_pathways=["pediatric", "respiratory"],
                required_capabilities=["oxygen", "pediatric"],
                required_specialists=["pediatrician", "emergency_physician"],
                summary="Pediatric respiratory distress requiring oxygen-capable ED.",
                rationale="Low oxygen saturation and severe wheeze.",
                confidence=0.9,
                source_model="fake-test-model",
            )
        if "crash" in text or "head injury" in text:
            return TriageSignal(
                acuity="red",
                care_pathways=["trauma"],
                required_capabilities=["icu", "oxygen", "ct", "surgical_team", "blood_bank"],
                required_specialists=["surgeon", "neurosurgeon", "anesthetist"],
                summary="Major trauma with suspected head injury and shock.",
                rationale="Low GCS, hypotension, tachycardia, and mechanism of injury.",
                confidence=0.93,
                source_model="fake-test-model",
            )
        return TriageSignal(
            acuity="red",
            care_pathways=["stroke"],
            required_capabilities=["icu", "oxygen", "ct"],
            required_specialists=["neurologist", "emergency_physician"],
            summary="Suspected acute stroke requiring CT-capable facility.",
            rationale="Focal neurologic deficit within thrombolysis time window.",
            confidence=0.89,
            source_model="fake-test-model",
        )

    async def generate_prealert(self, incident: Incident) -> str:
        return f"Pre-alert for {incident.id}: {incident.triage_signal.summary}"

    async def generate_handover(self, incident: Incident, request: HandoverRequest) -> str:
        return f"Situation: {incident.id}. Assessment: {incident.triage_signal.summary}. Treatment: test handover."


class UnavailableLLM(FakeLLM):
    async def triage_incident(self, incident: Incident) -> TriageSignal:
        raise LMStudioUnavailable("test server offline")

    async def generate_prealert(self, incident: Incident) -> str:
        raise LMStudioUnavailable("test server offline")

    async def generate_handover(self, incident: Incident, request: HandoverRequest) -> str:
        raise LMStudioUnavailable("test server offline")


@pytest.fixture()
def client() -> TestClient:
    app = create_app()
    app.state.llm_client = FakeLLM()
    return TestClient(app)


@pytest.fixture()
def unavailable_client() -> TestClient:
    app = create_app()
    app.state.llm_client = UnavailableLLM()
    return TestClient(app)


@pytest.fixture()
def stroke_payload() -> dict:
    return {
        "ambulance_id": "amb-accra-01",
        "scene_location": {
            "city": "Accra",
            "latitude": 5.5792,
            "longitude": -0.2057,
            "address": "Osu Oxford Street",
        },
        "patient": {
            "name": "Kwame Owusu",
            "ghana_card_id": "GHA-222333444-1",
            "nhis_id": "NHIS-AC-0002",
            "age": 61,
            "sex": "male",
            "chief_complaint": "Sudden right-sided weakness, facial droop, and slurred speech.",
            "notes": "Known atrial fibrillation.",
            "vitals": {
                "heart_rate": 112,
                "systolic_bp": 178,
                "diastolic_bp": 96,
                "respiratory_rate": 20,
                "oxygen_saturation": 94,
                "temperature_c": 36.9,
                "gcs": 14,
                "pain_score": 0,
            },
        },
    }

