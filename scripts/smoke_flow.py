from __future__ import annotations

import json
import os
from urllib.error import HTTPError
from urllib.request import Request, urlopen


BASE_URL = os.getenv("AAIS_BASE_URL", "http://127.0.0.1:8000").rstrip("/")


def main() -> None:
    payload = {
        "ambulance_id": "amb-accra-01",
        "scene_location": {
            "city": "Accra",
            "latitude": 5.5792,
            "longitude": -0.2057,
            "address": "Osu Oxford Street",
        },
        "patient": {
            "name": "Kwame Owusu",
            "ghana_card_id": "GHA-222333444-1",
            "nhis_id": "NHIS-AC-0002",
            "age": 61,
            "sex": "male",
            "chief_complaint": "Sudden right-sided weakness, facial droop, and slurred speech started 35 minutes ago.",
            "notes": "Known atrial fibrillation.",
            "vitals": {
                "heart_rate": 112,
                "systolic_bp": 178,
                "diastolic_bp": 96,
                "respiratory_rate": 20,
                "oxygen_saturation": 94,
                "temperature_c": 36.9,
                "gcs": 14,
                "pain_score": 0,
            },
        },
    }

    print(f"AAIS smoke flow against {BASE_URL}")
    print("health:", request("GET", "/health"))
    incident = request("POST", "/incidents", payload)
    incident_id = incident["id"]
    print("created:", incident_id)
    triaged = request("POST", f"/incidents/{incident_id}/ai-triage")
    print("triage:", triaged["triage_signal"]["summary"])
    ranked = request("POST", f"/incidents/{incident_id}/recommendations")
    top = next(item for item in ranked["recommendations"] if not item["blocked"])
    print("top hospital:", top["hospital_name"], top["score"])
    request("POST", f"/incidents/{incident_id}/destination", {"hospital_id": top["hospital_id"]})
    notified = request("POST", f"/incidents/{incident_id}/notify")
    print("notification:", notified["notification"]["status"])
    handover = request(
        "POST",
        f"/incidents/{incident_id}/handover",
        {
            "treatments_administered": ["oxygen applied", "IV access established"],
            "observations": "Patient remained under ambulance monitoring during transport.",
            "final_vitals": payload["patient"]["vitals"],
        },
    )
    print("handover:", handover["status"])
    overview = request("GET", "/command/overview")
    print("events:", len(overview["recent_events"]))


def request(method: str, path: str, body: dict | None = None) -> dict:
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = Request(
        f"{BASE_URL}{path}",
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urlopen(req, timeout=180) as response:  # noqa: S310 - local smoke script target.
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8")
        raise SystemExit(f"{method} {path} failed with {exc.code}: {detail}") from exc


if __name__ == "__main__":
    main()

