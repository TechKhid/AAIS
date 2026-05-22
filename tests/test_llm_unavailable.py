from __future__ import annotations


def test_llm_backed_endpoints_return_503_when_unavailable(unavailable_client, stroke_payload):
    incident_id = unavailable_client.post("/incidents", json=stroke_payload).json()["id"]

    response = unavailable_client.post(f"/incidents/{incident_id}/ai-triage")

    assert response.status_code == 503
    assert "LLM unavailable" in response.json()["detail"]

