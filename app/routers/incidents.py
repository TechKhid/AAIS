from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies import get_integrations, get_llm_client, get_routing_service, get_store
from app.schemas import (
    DestinationSelection,
    HandoverRequest,
    HandoverSummary,
    Incident,
    IncidentCreate,
    RecommendationResponse,
)
from app.services.llm_client import LMStudioClient, LLMResponseError, LMStudioUnavailable
from app.services.mocks import MockIntegrationService
from app.services.routing import ROUTING_WEIGHTS, RoutingService
from app.store import InMemoryStore

router = APIRouter(prefix="/incidents", tags=["incidents"])


@router.post("", response_model=Incident, status_code=status.HTTP_201_CREATED)
async def create_incident(
    payload: IncidentCreate,
    store: InMemoryStore = Depends(get_store),
) -> Incident:
    if payload.ambulance_id not in store.ambulances:
        raise HTTPException(status_code=404, detail=f"Unknown ambulance: {payload.ambulance_id}")
    patient = payload.patient
    patient_record = store.find_patient_record(patient.ghana_card_id, patient.nhis_id, patient.patient_id)
    return store.create_incident(payload, patient_record)


@router.get("/{incident_id}", response_model=Incident)
async def get_incident(incident_id: str, store: InMemoryStore = Depends(get_store)) -> Incident:
    return _require_incident(store, incident_id)


@router.post("/{incident_id}/ai-triage", response_model=Incident)
async def ai_triage(
    incident_id: str,
    store: InMemoryStore = Depends(get_store),
    llm_client: LMStudioClient = Depends(get_llm_client),
) -> Incident:
    incident = _require_incident(store, incident_id)
    try:
        triage = await llm_client.triage_incident(incident)
    except LMStudioUnavailable as exc:
        raise HTTPException(status_code=503, detail=f"LLM unavailable: {exc}") from exc
    except LLMResponseError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return store.set_triage(incident_id, triage)


@router.post("/{incident_id}/recommendations", response_model=RecommendationResponse)
async def recommendations(
    incident_id: str,
    store: InMemoryStore = Depends(get_store),
    routing_service: RoutingService = Depends(get_routing_service),
) -> RecommendationResponse:
    incident = _require_incident(store, incident_id)
    if not incident.triage_signal:
        raise HTTPException(status_code=409, detail="AI triage is required before recommendations.")
    recommendations_result = routing_service.rank_hospitals(incident)
    store.set_recommendations(incident_id, recommendations_result)
    return RecommendationResponse(
        incident_id=incident_id,
        weights=ROUTING_WEIGHTS,
        recommendations=recommendations_result,
    )


@router.post("/{incident_id}/destination", response_model=Incident)
async def select_destination(
    incident_id: str,
    payload: DestinationSelection,
    store: InMemoryStore = Depends(get_store),
) -> Incident:
    incident = _require_incident(store, incident_id)
    if not incident.recommendations:
        raise HTTPException(status_code=409, detail="Recommendations are required before destination selection.")
    candidates = {recommendation.hospital_id: recommendation for recommendation in incident.recommendations}
    if payload.hospital_id not in candidates:
        raise HTTPException(status_code=400, detail="Selected hospital was not in the recommendation set.")
    if candidates[payload.hospital_id].blocked:
        raise HTTPException(status_code=409, detail="Selected hospital is blocked by a critical missing capability.")
    return store.set_destination(incident_id, payload.hospital_id)


@router.post("/{incident_id}/notify", response_model=Incident)
async def notify_hospital(
    incident_id: str,
    store: InMemoryStore = Depends(get_store),
    llm_client: LMStudioClient = Depends(get_llm_client),
    integrations: MockIntegrationService = Depends(get_integrations),
) -> Incident:
    incident = _require_incident(store, incident_id)
    if not incident.selected_hospital_id:
        raise HTTPException(status_code=409, detail="Destination must be confirmed before hospital notification.")
    if not incident.triage_signal:
        raise HTTPException(status_code=409, detail="AI triage is required before hospital notification.")
    hospital = store.hospitals[incident.selected_hospital_id]
    try:
        summary = await llm_client.generate_prealert(incident)
    except LMStudioUnavailable as exc:
        raise HTTPException(status_code=503, detail=f"LLM unavailable: {exc}") from exc
    except LLMResponseError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    notification = integrations.send_prealert(incident, hospital, summary)
    return store.set_notification(incident_id, notification)


@router.post("/{incident_id}/handover", response_model=Incident)
async def handover(
    incident_id: str,
    payload: HandoverRequest,
    store: InMemoryStore = Depends(get_store),
    llm_client: LMStudioClient = Depends(get_llm_client),
) -> Incident:
    incident = _require_incident(store, incident_id)
    if not incident.selected_hospital_id:
        raise HTTPException(status_code=409, detail="Destination must be confirmed before handover.")
    try:
        summary = await llm_client.generate_handover(incident, payload)
    except LMStudioUnavailable as exc:
        raise HTTPException(status_code=503, detail=f"LLM unavailable: {exc}") from exc
    except LLMResponseError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    handover_summary = HandoverSummary(
        incident_id=incident_id,
        hospital_id=incident.selected_hospital_id,
        summary=summary,
    )
    return store.set_handover(incident_id, handover_summary)


def _require_incident(store: InMemoryStore, incident_id: str) -> Incident:
    incident = store.get_incident(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail=f"Incident not found: {incident_id}")
    return incident

