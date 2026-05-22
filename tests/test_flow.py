from __future__ import annotations


def test_full_happy_path_flow(client, stroke_payload):
    created = client.post("/incidents", json=stroke_payload)
    assert created.status_code == 201
    incident_id = created.json()["id"]
    assert created.json()["patient_record"]["patient_id"] == "FHIR-PAT-1002"

    triaged = client.post(f"/incidents/{incident_id}/ai-triage")
    assert triaged.status_code == 200
    assert triaged.json()["triage_signal"]["care_pathways"] == ["stroke"]

    ranked = client.post(f"/incidents/{incident_id}/recommendations")
    assert ranked.status_code == 200
    recommendations = ranked.json()["recommendations"]
    first = next(item for item in recommendations if not item["blocked"])
    assert first["score"] > 0
    assert "ct" in first["matched_requirements"]

    selected = client.post(f"/incidents/{incident_id}/destination", json={"hospital_id": first["hospital_id"]})
    assert selected.status_code == 200
    assert selected.json()["status"] == "destination_confirmed"

    notified = client.post(f"/incidents/{incident_id}/notify")
    assert notified.status_code == 200
    assert notified.json()["notification"]["status"] == "sent"

    handover = client.post(
        f"/incidents/{incident_id}/handover",
        json={
            "treatments_administered": ["oxygen applied", "IV access established"],
            "observations": "No deterioration in transit.",
            "final_vitals": stroke_payload["patient"]["vitals"],
        },
    )
    assert handover.status_code == 200
    assert handover.json()["status"] == "handover_complete"

    overview = client.get("/command/overview")
    assert overview.status_code == 200
    event_types = [event["event_type"] for event in overview.json()["recent_events"]]
    assert "incident.handover_complete" in event_types


def test_recommendations_require_ai_triage(client, stroke_payload):
    created = client.post("/incidents", json=stroke_payload)
    incident_id = created.json()["id"]

    response = client.post(f"/incidents/{incident_id}/recommendations")

    assert response.status_code == 409
    assert "AI triage is required" in response.json()["detail"]

