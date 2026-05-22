from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.dependencies import get_llm_client
from app.schemas import HealthResponse
from app.services.llm_client import LMStudioClient

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health(request: Request, llm_client: LMStudioClient = Depends(get_llm_client)) -> HealthResponse:
    llm_health = await llm_client.health()
    settings = request.app.state.settings
    return HealthResponse(
        app=settings.app_name,
        status="ok",
        lmstudio_available=llm_health["available"],
        lmstudio_base_url=settings.lmstudio_base_url,
        lmstudio_model=settings.lmstudio_model,
        lmstudio_resolved_model=llm_health.get("resolved_model"),
        lmstudio_models=llm_health["models"],
        detail=llm_health["detail"],
    )
