from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import get_store
from app.schemas import Ambulance, AmbulanceLocationUpdate
from app.store import InMemoryStore

router = APIRouter(prefix="/ambulances", tags=["ambulances"])


@router.get("", response_model=list[Ambulance])
async def list_ambulances(store: InMemoryStore = Depends(get_store)) -> list[Ambulance]:
    return list(store.ambulances.values())


@router.patch("/{ambulance_id}/location", response_model=Ambulance)
async def update_location(
    ambulance_id: str,
    payload: AmbulanceLocationUpdate,
    store: InMemoryStore = Depends(get_store),
) -> Ambulance:
    ambulance = store.ambulances.get(ambulance_id)
    if not ambulance:
        raise HTTPException(status_code=404, detail=f"Ambulance not found: {ambulance_id}")
    update = {}
    if payload.status is not None:
        update["status"] = payload.status
    if payload.location is not None:
        update["location"] = payload.location
    updated = store.update_ambulance(ambulance.model_copy(update=update))
    store.record_event(
        event_type="ambulance.location_updated",
        actor=ambulance_id,
        message=f"{updated.call_sign} updated location/status.",
        related_ids={"ambulance_id": ambulance_id},
        payload=updated.model_dump(mode="json"),
    )
    return updated

