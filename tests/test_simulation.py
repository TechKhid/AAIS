from __future__ import annotations


def test_simulation_lists_scenarios(client):
    response = client.get("/simulation/scenarios")

    assert response.status_code == 200
    scenarios = response.json()
    assert len(scenarios) >= 5
    assert {scenario["id"] for scenario in scenarios} >= {"accra-stroke", "tamale-pediatric-respiratory"}


def test_simulation_run_completes_with_stubbed_llm(client):
    created = client.post("/simulation/sessions", json={"scenario_id": "accra-stroke"})
    assert created.status_code == 201
    session_id = created.json()["id"]

    result = client.post(f"/simulation/sessions/{session_id}/run")

    assert result.status_code == 200
    body = result.json()
    assert body["session"]["status"] == "completed"
    assert body["incident"]["status"] == "handover_complete"
    assert body["incident"]["triage_signal"]["care_pathways"] == ["stroke"]
    assert body["incident"]["selected_hospital_id"]
    assert all(step["status"] == "complete" for step in body["session"]["steps"])


def test_simulation_pauses_when_llm_unavailable(unavailable_client):
    created = unavailable_client.post("/simulation/sessions", json={"scenario_id": "accra-stroke"})
    session_id = created.json()["id"]

    dispatch = unavailable_client.post(f"/simulation/sessions/{session_id}/step")
    assert dispatch.status_code == 200
    assert dispatch.json()["session"]["status"] == "running"

    triage = unavailable_client.post(f"/simulation/sessions/{session_id}/step")

    assert triage.status_code == 200
    body = triage.json()
    assert body["session"]["status"] == "paused"
    assert "LLM unavailable" in body["session"]["last_error"]
    assert body["session"]["steps"][1]["status"] == "paused"


def test_simulation_reset_clears_sessions_and_incidents(client):
    client.post("/simulation/sessions", json={"scenario_id": "accra-stroke"})

    reset = client.post("/simulation/reset")
    sessions = client.get("/simulation/sessions")
    overview = client.get("/command/overview")

    assert reset.status_code == 200
    assert sessions.json() == []
    assert overview.json()["active_incidents"] == []

