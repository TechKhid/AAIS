from __future__ import annotations

from fastapi import Request

from app.services.llm_client import LMStudioClient
from app.services.mocks import MockIntegrationService
from app.services.routing import RoutingService
from app.services.simulation import SimulationEngine
from app.store import InMemoryStore


def get_store(request: Request) -> InMemoryStore:
    return request.app.state.store


def get_llm_client(request: Request) -> LMStudioClient:
    return request.app.state.llm_client


def get_integrations(request: Request) -> MockIntegrationService:
    return request.app.state.integrations


def get_routing_service(request: Request) -> RoutingService:
    return request.app.state.routing_service


def get_simulation_engine(request: Request) -> SimulationEngine:
    return SimulationEngine(
        request.app.state.store,
        request.app.state.integrations,
        request.app.state.routing_service,
        request.app.state.llm_client,
    )
