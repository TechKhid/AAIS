from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.dependencies import get_store
from app.schemas import CommandOverview, EventRecord
from app.store import InMemoryStore

router = APIRouter(prefix="/command", tags=["command center"])


@router.get("/overview", response_model=CommandOverview)
async def overview(store: InMemoryStore = Depends(get_store)) -> CommandOverview:
    active_incidents = [
        incident
        for incident in store.incidents.values()
        if incident.status != "handover_complete"
    ]
    return CommandOverview(
        active_incidents=active_incidents,
        ambulances=list(store.ambulances.values()),
        hospitals=list(store.hospitals.values()),
        recent_events=store.list_events(limit=25),
    )


@router.get("/events", response_model=list[EventRecord])
async def events(
    limit: int = Query(default=100, ge=1, le=500),
    store: InMemoryStore = Depends(get_store),
) -> list[EventRecord]:
    return store.list_events(limit=limit)

