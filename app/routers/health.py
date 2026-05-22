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
    llm_provider = llm_health.get("provider", settings.llm_provider)
    llm_base_url = llm_health.get("base_url", settings.lmstudio_base_url)
    llm_model = llm_health.get("model", settings.lmstudio_model)
    resolved_model = llm_health.get("resolved_model")
    models = llm_health.get("models", [])
    return HealthResponse(
        app=settings.app_name,
        status="ok",
        llm_provider=llm_provider,
        llm_available=llm_health["available"],
        llm_base_url=llm_base_url,
        llm_model=llm_model,
        llm_resolved_model=resolved_model,
        llm_models=models,
        lmstudio_available=llm_health["available"],
        lmstudio_base_url=llm_base_url,
        lmstudio_model=llm_model,
        lmstudio_resolved_model=resolved_model,
        lmstudio_models=models,
        detail=llm_health["detail"],
    )
