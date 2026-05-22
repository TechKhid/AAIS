from __future__ import annotations


def test_health_reports_llm_status(client):
    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["lmstudio_available"] is True
    assert body["lmstudio_model"]


def test_overview_starts_with_seeded_assets(client):
    response = client.get("/command/overview")

    assert response.status_code == 200
    body = response.json()
    assert len(body["hospitals"]) >= 9
    assert len(body["ambulances"]) >= 4
    assert body["recent_events"][0]["event_type"] == "system.boot"
