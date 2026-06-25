from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app


def test_health_reports_llm_status(client):
    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["llm_provider"] == "lmstudio"
    assert body["llm_available"] is True
    assert body["llm_model"]
    assert body["lmstudio_available"] is True
    assert body["lmstudio_model"]


def test_live_does_not_depend_on_llm(client):
    response = client.get("/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_reports_nim_without_claiming_lmstudio_available():
    class FakeNimLLM:
        async def health(self) -> dict:
            return {
                "provider": "nvidia_nim",
                "base_url": "https://integrate.api.nvidia.com/v1",
                "model": "nvidia/nemotron-3-super-120b-a12b",
                "available": True,
                "models": ["nvidia/nemotron-3-super-120b-a12b"],
                "resolved_model": "nvidia/nemotron-3-super-120b-a12b",
                "detail": None,
            }

    app = create_app()
    app.state.llm_client = FakeNimLLM()
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["llm_provider"] == "nvidia_nim"
    assert body["llm_available"] is True
    assert body["llm_model"] == "nvidia/nemotron-3-super-120b-a12b"
    assert body["lmstudio_available"] is False
    assert body["lmstudio_base_url"] == "http://127.0.0.1:1234/v1"


def test_overview_starts_with_seeded_assets(client):
    response = client.get("/command/overview")

    assert response.status_code == 200
    body = response.json()
    assert len(body["hospitals"]) >= 9
    assert len(body["ambulances"]) >= 4
    assert body["recent_events"][0]["event_type"] == "system.boot"
