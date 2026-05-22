from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

from dotenv import load_dotenv


LLMProvider = Literal["lmstudio", "nvidia_nim"]


@dataclass(frozen=True)
class Settings:
    app_name: str = "AAIS MVP"
    llm_provider: LLMProvider = "lmstudio"
    lmstudio_base_url: str = "http://127.0.0.1:1234/v1"
    lmstudio_model: str = "qwen/qwen3.5-9b"
    nvidia_nim_base_url: str = "https://integrate.api.nvidia.com/v1"
    nvidia_nim_model: str = "meta/llama-3.1-8b-instruct"
    nvidia_nim_api_key: str | None = None
    llm_timeout_seconds: float = 30.0


def get_settings() -> Settings:
    load_dotenv()
    return Settings(
        llm_provider=_normalize_llm_provider(os.getenv("LLM_PROVIDER", "lmstudio")),
        lmstudio_base_url=os.getenv("LMSTUDIO_BASE_URL", "http://127.0.0.1:1234/v1").rstrip("/"),
        lmstudio_model=os.getenv("LMSTUDIO_MODEL", "qwen/qwen3.5-9b"),
        nvidia_nim_base_url=os.getenv("NVIDIA_NIM_BASE_URL", "https://integrate.api.nvidia.com/v1").rstrip("/"),
        nvidia_nim_model=os.getenv("NVIDIA_NIM_MODEL", "meta/llama-3.1-8b-instruct"),
        nvidia_nim_api_key=(
            os.getenv("NVIDIA_NIM_API_KEY")
            or os.getenv("NVIDIA_API_KEY")
            or os.getenv("NIM_API_KEY")
            or None
        ),
        llm_timeout_seconds=float(os.getenv("LLM_TIMEOUT_SECONDS", "30")),
    )


def _normalize_llm_provider(value: str) -> LLMProvider:
    normalized = value.strip().lower().replace("-", "_")
    aliases = {
        "lmstudio": "lmstudio",
        "lm_studio": "lmstudio",
        "local": "lmstudio",
        "nvidia": "nvidia_nim",
        "nim": "nvidia_nim",
        "nvidia_nim": "nvidia_nim",
    }
    provider = aliases.get(normalized)
    if provider is None:
        raise ValueError(f"Unsupported LLM_PROVIDER {value!r}. Use 'lmstudio' or 'nvidia_nim'.")
    return provider
