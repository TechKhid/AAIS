from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    app_name: str = "AAIS MVP"
    lmstudio_base_url: str = "http://127.0.0.1:1234/v1"
    lmstudio_model: str = "qwen/qwen3.5-9b"
    llm_timeout_seconds: float = 30.0


def get_settings() -> Settings:
    load_dotenv()
    return Settings(
        lmstudio_base_url=os.getenv("LMSTUDIO_BASE_URL", "http://127.0.0.1:1234/v1").rstrip("/"),
        lmstudio_model=os.getenv("LMSTUDIO_MODEL", "qwen/qwen3.5-9b"),
        llm_timeout_seconds=float(os.getenv("LLM_TIMEOUT_SECONDS", "30")),
    )

