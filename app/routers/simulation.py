from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.dependencies import get_simulation_engine, get_store
from app.schemas import SimulationScenario, SimulationSession, SimulationStartRequest, SimulationStepResult
from app.services.simulation import SimulationEngine
from app.store import InMemoryStore

router = APIRouter(prefix="/simulation", tags=["simulation"])


@router.get("/scenarios", response_model=list[SimulationScenario])
async def list_scenarios(engine: SimulationEngine = Depends(get_simulation_engine)) -> list[SimulationScenario]:
    return engine.list_scenarios()


@router.get("/sessions", response_model=list[SimulationSession])
async def list_sessions(store: InMemoryStore = Depends(get_store)) -> list[SimulationSession]:
    return store.list_simulation_sessions()


@router.post("/sessions", response_model=SimulationSession, status_code=status.HTTP_201_CREATED)
async def start_session(
    payload: SimulationStartRequest,
    engine: SimulationEngine = Depends(get_simulation_engine),
) -> SimulationSession:
    try:
        return engine.start(payload.scenario_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Scenario not found: {payload.scenario_id}") from exc


@router.get("/sessions/{session_id}", response_model=SimulationSession)
async def get_session(session_id: str, store: InMemoryStore = Depends(get_store)) -> SimulationSession:
    session = store.get_simulation_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Simulation session not found: {session_id}")
    return session


@router.post("/sessions/{session_id}/step", response_model=SimulationStepResult)
async def step_session(
    session_id: str,
    engine: SimulationEngine = Depends(get_simulation_engine),
) -> SimulationStepResult:
    try:
        return await engine.step(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Simulation session not found: {session_id}") from exc


@router.post("/sessions/{session_id}/run", response_model=SimulationStepResult)
async def run_session(
    session_id: str,
    max_steps: int = Query(default=10, ge=1, le=20),
    engine: SimulationEngine = Depends(get_simulation_engine),
) -> SimulationStepResult:
    try:
        return await engine.run(session_id, max_steps=max_steps)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Simulation session not found: {session_id}") from exc


@router.post("/reset", response_model=dict[str, str])
async def reset_simulation(store: InMemoryStore = Depends(get_store)) -> dict[str, str]:
    store.reset()
    return {"status": "reset"}

