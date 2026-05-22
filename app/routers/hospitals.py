from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.dependencies import get_store
from app.schemas import CapacityStatus, Hospital
from app.store import InMemoryStore

router = APIRouter(prefix="/hospitals", tags=["hospitals"])


@router.get("", response_model=list[Hospital])
async def list_hospitals(store: InMemoryStore = Depends(get_store)) -> list[Hospital]:
    return list(store.hospitals.values())


@router.patch("/{hospital_id}/capacity", response_model=Hospital)
async def update_capacity(
    hospital_id: str,
    payload: CapacityStatus,
    store: InMemoryStore = Depends(get_store),
) -> Hospital:
    hospital = store.update_capacity(hospital_id, payload)
    if not hospital:
        raise HTTPException(status_code=404, detail=f"Hospital not found: {hospital_id}")
    return hospital

