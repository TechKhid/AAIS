from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.routers import ambulances, command, health, hospitals, incidents, simulation
from app.services.llm_client import LMStudioClient
from app.services.mocks import MockIntegrationService
from app.services.routing import RoutingService
from app.services.simulation import SimulationEngine
from app.store import InMemoryStore


def create_app() -> FastAPI:
    settings = get_settings()
    store = InMemoryStore()
    integrations = MockIntegrationService(store)
    routing_service = RoutingService(store, integrations)
    llm_client = LMStudioClient(settings)
    simulation_engine = SimulationEngine(store, integrations, routing_service, llm_client)

    api = FastAPI(
        title="AI-Powered Ambulance Intelligence System MVP",
        version="0.1.0",
        description=(
            "API-first simulator for Ghana emergency response coordination. "
            "Stakeholder systems are mocked; LM Studio or NVIDIA NIM can provide triage and handover assistance."
        ),
    )
    api.state.settings = settings
    api.state.store = store
    api.state.integrations = integrations
    api.state.routing_service = routing_service
    api.state.llm_client = llm_client
    api.state.simulation_engine = simulation_engine

    api.include_router(health.router)
    api.include_router(incidents.router)
    api.include_router(hospitals.router)
    api.include_router(ambulances.router)
    api.include_router(command.router)
    api.include_router(simulation.router)

    static_dir = Path(__file__).parent / "static"
    api.mount("/static", StaticFiles(directory=static_dir), name="static")

    @api.get("/", include_in_schema=False)
    async def demo_console() -> FileResponse:
        return FileResponse(static_dir / "index.html")

    return api


app = create_app()
