from __future__ import annotations

from app.schemas import TriageSignal


def test_routing_is_deterministic_for_equivalent_triage(client, stroke_payload):
    incident_id = client.post("/incidents", json=stroke_payload).json()["id"]
    incident = client.post(f"/incidents/{incident_id}/ai-triage").json()
    first_rank = client.post(f"/incidents/{incident_id}/recommendations").json()["recommendations"]

    store = client.app.state.store
    stored = store.get_incident(incident_id)
    equivalent = TriageSignal(
        acuity=incident["triage_signal"]["acuity"],
        care_pathways=["stroke"],
        required_capabilities=["oxygen", "ct", "icu"],
        required_specialists=["emergency_physician", "neurologist"],
        summary="Different wording for the same structured signal.",
        rationale="Different rationale wording.",
        confidence=0.72,
        source_model="fake-test-model",
    )
    store.set_triage(incident_id, equivalent)
    second_rank = client.post(f"/incidents/{incident_id}/recommendations").json()["recommendations"]

    assert [item["hospital_id"] for item in first_rank] == [item["hospital_id"] for item in second_rank]
    assert stored is not None


def test_recommendations_are_limited_to_incident_region(client, stroke_payload):
    incident_id = client.post("/incidents", json=stroke_payload).json()["id"]
    client.post(f"/incidents/{incident_id}/ai-triage")

    response = client.post(f"/incidents/{incident_id}/recommendations")

    assert response.status_code == 200
    recommendations = response.json()["recommendations"]
    assert recommendations
    assert {item["city"] for item in recommendations} == {"Accra"}
    assert {item["hospital_id"] for item in recommendations} <= {"korle-bu-teaching", "ridge-hospital", "37-military"}


def test_kumasi_incident_only_recommends_kumasi_hospitals(client):
    payload = {
        "ambulance_id": "amb-kumasi-01",
        "scene_location": {
            "city": "Kumasi",
            "latitude": 6.6666,
            "longitude": -1.6163,
            "address": "Adum market area",
        },
        "patient": {
            "age": 54,
            "sex": "female",
            "chief_complaint": "Crushing central chest pain with sweating and nausea for 40 minutes.",
            "notes": "Pain radiates to left arm. No known allergies.",
            "vitals": {
                "heart_rate": 104,
                "systolic_bp": 150,
                "diastolic_bp": 88,
                "respiratory_rate": 22,
                "oxygen_saturation": 95,
                "temperature_c": 36.7,
                "gcs": 15,
                "pain_score": 9,
            },
        },
    }
    incident_id = client.post("/incidents", json=payload).json()["id"]
    client.post(f"/incidents/{incident_id}/ai-triage")

    recommendations = client.post(f"/incidents/{incident_id}/recommendations").json()["recommendations"]

    assert recommendations
    assert {item["city"] for item in recommendations} == {"Kumasi"}
    assert {item["hospital_id"] for item in recommendations} <= {"komfo-anokye", "kumasi-south", "suntreso-hospital"}


def test_capacity_update_changes_obstetric_recommendation(client):
    payload = {
        "ambulance_id": "amb-accra-02",
        "scene_location": {
            "city": "Accra",
            "latitude": 5.5486,
            "longitude": -0.2012,
            "address": "Jamestown clinic transfer",
        },
        "patient": {
            "name": "Ama Serwaa",
            "ghana_card_id": "GHA-123456789-0",
            "nhis_id": "NHIS-AC-0001",
            "age": 34,
            "sex": "female",
            "chief_complaint": "Thirty-six weeks pregnant with heavy vaginal bleeding and dizziness.",
            "notes": "Possible placental abruption.",
            "vitals": {
                "heart_rate": 124,
                "systolic_bp": 92,
                "diastolic_bp": 58,
                "respiratory_rate": 24,
                "oxygen_saturation": 96,
                "temperature_c": 36.8,
                "gcs": 15,
                "pain_score": 7,
            },
        },
    }
    incident_id = client.post("/incidents", json=payload).json()["id"]
    client.post(f"/incidents/{incident_id}/ai-triage")
    before = client.post(f"/incidents/{incident_id}/recommendations").json()["recommendations"]
    first_before = next(item for item in before if not item["blocked"])["hospital_id"]

    ridge = client.get("/hospitals").json()
    ridge_capacity = next(item for item in ridge if item["id"] == "ridge-hospital")["capacity"]
    ridge_capacity["maternity_beds_available"] = 0
    ridge_capacity["neonatal_support_available"] = False
    ridge_capacity["blood_bank_available"] = False
    client.patch("/hospitals/ridge-hospital/capacity", json=ridge_capacity)

    after = client.post(f"/incidents/{incident_id}/recommendations").json()["recommendations"]
    first_after = next(item for item in after if not item["blocked"])["hospital_id"]

    assert first_before == "ridge-hospital"
    assert first_after != "ridge-hospital"
