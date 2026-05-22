from __future__ import annotations

import argparse
import asyncio
import os
import sys
from dataclasses import replace
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

import httpx
from dotenv import load_dotenv

from app.config import Settings
from app.schemas import Incident, Location, PatientSnapshot, Vitals
from app.services.llm_client import LMStudioClient


DEFAULT_MODELS = [
    "nvidia/nemotron-3-super-120b-a12b",
    "deepseek-ai/deepseek-v4-flash",
]


async def main() -> None:
    load_dotenv(ROOT_DIR / ".env")

    parser = argparse.ArgumentParser(description="Smoke test NVIDIA NIM chat models through the AAIS LLM client.")
    parser.add_argument(
        "models",
        nargs="*",
        default=DEFAULT_MODELS,
        help="NVIDIA NIM model ids to test.",
    )
    parser.add_argument(
        "--prompt",
        default="Reply with one concise sentence confirming you can support AAIS emergency triage testing.",
        help="Short chat prompt to send to each model.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=float(os.getenv("LLM_TIMEOUT_SECONDS", "30")),
        help="Per-request LLM timeout.",
    )
    parser.add_argument(
        "--health-only",
        action="store_true",
        help="Only check /models health and skip chat completions.",
    )
    parser.add_argument(
        "--client-chat",
        action="store_true",
        help="Use the AAIS LLM client for chat instead of the direct HTTP smoke request.",
    )
    parser.add_argument(
        "--triage",
        action="store_true",
        help="Run the AAIS structured triage extraction path instead of a simple chat prompt.",
    )
    args = parser.parse_args()

    api_key = os.getenv("NVIDIA_NIM_API_KEY") or os.getenv("NVIDIA_API_KEY") or os.getenv("NIM_API_KEY")
    if not api_key:
        raise SystemExit("Set NVIDIA_NIM_API_KEY, NVIDIA_API_KEY, or NIM_API_KEY before running this script.")

    base_settings = Settings(
        llm_provider="nvidia_nim",
        nvidia_nim_base_url=os.getenv("NVIDIA_NIM_BASE_URL", "https://integrate.api.nvidia.com/v1").rstrip("/"),
        nvidia_nim_api_key=api_key,
        llm_timeout_seconds=args.timeout_seconds,
    )

    for model in args.models:
        settings = replace(base_settings, nvidia_nim_model=model)
        client = LMStudioClient(settings)
        print(f"model={model}", flush=True)
        health = await client.health()
        print(f"  health_available={health['available']}", flush=True)
        print(f"  health_detail={health['detail'] or 'ok'}", flush=True)
        if not health["available"] or args.health_only:
            continue
        try:
            if args.triage:
                triage = await asyncio.wait_for(
                    client.triage_incident(sample_stroke_incident()),
                    timeout=args.timeout_seconds + 10,
                )
                text = (
                    f"acuity={triage.acuity}; pathways={','.join(triage.care_pathways)}; "
                    f"capabilities={','.join(triage.required_capabilities)}; "
                    f"specialists={','.join(triage.required_specialists)}"
                )
            elif args.client_chat:
                text = await asyncio.wait_for(
                    client._chat_text(
                        system="You are a concise assistant used for a provider connectivity smoke test.",
                        user=args.prompt,
                    ),
                    timeout=args.timeout_seconds + 5,
                )
            else:
                text = await nim_chat_completion(
                    base_url=settings.nvidia_nim_base_url,
                    api_key=api_key,
                    model=model,
                    prompt=args.prompt,
                    timeout_seconds=args.timeout_seconds,
                )
        except Exception as exc:  # noqa: BLE001 - smoke script should report and continue to next model.
            print(f"  chat_error={type(exc).__name__}: {exc}", flush=True)
            continue
        print(f"  response={text[:500]}", flush=True)


async def nim_chat_completion(
    base_url: str,
    api_key: str,
    model: str,
    prompt: str,
    timeout_seconds: float,
) -> str:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a concise assistant used for a provider connectivity smoke test."},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": 80,
        "temperature": 0.1,
    }
    async with httpx.AsyncClient(timeout=timeout_seconds) as client:
        response = await client.post(
            f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
        )
    response.raise_for_status()
    body = response.json()
    return body["choices"][0]["message"]["content"].strip()


def sample_stroke_incident() -> Incident:
    return Incident(
        id="inc-nim-smoke",
        ambulance_id="amb-accra-01",
        scene_location=Location(city="Accra", latitude=5.5792, longitude=-0.2057, address="Osu Oxford Street"),
        patient=PatientSnapshot(
            name="Kwame Owusu",
            ghana_card_id="GHA-222333444-1",
            nhis_id="NHIS-AC-0002",
            age=61,
            sex="male",
            chief_complaint="Sudden right-sided weakness, facial droop, and slurred speech started 35 minutes ago.",
            notes="Known atrial fibrillation.",
            vitals=Vitals(
                heart_rate=112,
                systolic_bp=178,
                diastolic_bp=96,
                respiratory_rate=20,
                oxygen_saturation=94,
                temperature_c=36.9,
                gcs=14,
                pain_score=0,
            ),
        ),
    )


if __name__ == "__main__":
    asyncio.run(main())
