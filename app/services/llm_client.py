from __future__ import annotations

import json
import re
from types import SimpleNamespace
from typing import Any

import httpx
from openai import APIConnectionError, APIError, APITimeoutError, AsyncOpenAI, BadRequestError
from pydantic import ValidationError

from app.config import Settings
from app.schemas import HandoverRequest, Incident, TriageSignal


class LMStudioUnavailable(Exception):
    pass


class LLMResponseError(Exception):
    pass


class LMStudioClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.provider = settings.llm_provider
        self.provider_label = _provider_label(settings.llm_provider)
        self.base_url = _provider_base_url(settings)
        self.model = _provider_model(settings)
        self.api_key = _provider_api_key(settings)
        self.resolved_model = self.model
        self.client = AsyncOpenAI(
            base_url=self.base_url,
            api_key=self.api_key or "not-used",
            timeout=settings.llm_timeout_seconds,
            max_retries=0,
        )

    async def health(self) -> dict[str, Any]:
        if self.provider == "nvidia_nim":
            return await self._nvidia_nim_health()
        return await self._lmstudio_health()

    async def _lmstudio_health(self) -> dict[str, Any]:
        v1_url = f"{self.base_url}/models"
        v0_url = self.base_url.replace("/v1", "/api/v0") + "/models"
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                v0_response = await client.get(v0_url)
                if v0_response.status_code == 200:
                    body = v0_response.json()
                    models = [item.get("id", "") for item in body.get("data", []) if item.get("id")]
                    aliases = _model_aliases(self.model)
                    configured = next(
                        (item for item in body.get("data", []) if item.get("id") in aliases),
                        None,
                    )
                    if configured:
                        state = configured.get("state", "unknown")
                        resolved_model = configured.get("id", self.model)
                        self.resolved_model = resolved_model
                        detail = None
                        if state != "loaded":
                            detail = f"Configured model is {state}. Load it in LM Studio or set LMSTUDIO_MODEL."
                        elif resolved_model != self.model:
                            detail = f"Using loaded LM Studio model {resolved_model} for configured {self.model}."
                        return self._health_payload(
                            available=state == "loaded",
                            models=models,
                            resolved_model=resolved_model,
                            detail=detail,
                        )

                response = await client.get(v1_url)
                response.raise_for_status()
        except Exception as exc:  # noqa: BLE001 - health should convert all connection failures.
            return self._health_payload(
                available=False,
                models=[],
                resolved_model=self.resolved_model,
                detail=f"LM Studio unavailable: {exc}",
            )

        body = response.json()
        models = [item.get("id", "") for item in body.get("data", []) if item.get("id")]
        aliases = _model_aliases(self.model)
        resolved_model = next((model for model in models if model in aliases), self.model)
        self.resolved_model = resolved_model
        is_available = resolved_model in models
        return self._health_payload(
            available=is_available,
            models=models,
            resolved_model=resolved_model,
            detail=None if is_available else "Configured model not listed by LM Studio.",
        )

    async def _nvidia_nim_health(self) -> dict[str, Any]:
        if _hosted_nvidia_nim(self.base_url) and not self.settings.nvidia_nim_api_key:
            return self._health_payload(
                available=False,
                models=[],
                resolved_model=self.resolved_model,
                detail="NVIDIA NIM API key missing. Set NVIDIA_NIM_API_KEY or NVIDIA_API_KEY.",
            )

        headers = _auth_headers(self.api_key)
        ready_url = f"{self.base_url}/health/ready"
        models_url = f"{self.base_url}/models"

        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                if not _hosted_nvidia_nim(self.base_url):
                    ready_response = await client.get(ready_url, headers=headers)
                    if ready_response.status_code >= 400:
                        return self._health_payload(
                            available=False,
                            models=[],
                            resolved_model=self.resolved_model,
                            detail=f"NVIDIA NIM is not ready: HTTP {ready_response.status_code}.",
                        )

                response = await client.get(models_url, headers=headers)
                if response.status_code in {401, 403}:
                    return self._health_payload(
                        available=False,
                        models=[],
                        resolved_model=self.resolved_model,
                        detail="NVIDIA NIM authentication failed. Check NVIDIA_NIM_API_KEY or NVIDIA_API_KEY.",
                    )
                response.raise_for_status()
        except Exception as exc:  # noqa: BLE001 - health should convert all connection failures.
            return self._health_payload(
                available=False,
                models=[],
                resolved_model=self.resolved_model,
                detail=f"NVIDIA NIM unavailable: {exc}",
            )

        body = response.json()
        models = [item.get("id", "") for item in body.get("data", []) if item.get("id")]
        aliases = _model_aliases(self.model)
        resolved_model = next((model for model in models if model in aliases), self.model)
        self.resolved_model = resolved_model
        is_available = resolved_model in models
        return self._health_payload(
            available=is_available,
            models=models,
            resolved_model=resolved_model,
            detail=None if is_available else "Configured NVIDIA NIM model not listed by /models.",
        )

    def _health_payload(
        self,
        available: bool,
        models: list[str],
        resolved_model: str | None,
        detail: str | None,
    ) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "provider_label": self.provider_label,
            "base_url": self.base_url,
            "model": self.model,
            "available": available,
            "models": models,
            "resolved_model": resolved_model,
            "detail": detail,
        }

    async def triage_incident(self, incident: Incident) -> TriageSignal:
        await self.ensure_available()
        patient_json = incident.patient.model_dump(mode="json")
        record_json = incident.patient_record.model_dump(mode="json") if incident.patient_record else None
        system = (
            "You are an emergency medical decision-support assistant for an ambulance coordination simulator. "
            "Extract triage signals from the ambulance note. You do not choose the hospital. "
            "Return only one valid JSON object. Do not include markdown, commentary, XML, chain-of-thought, or analysis text. "
            "The first character of your response must be { and the final character must be }."
        )
        user = {
            "task": "Create structured triage decision-support data for routing.",
            "allowed_acuity": ["red", "orange", "yellow", "green"],
            "allowed_care_pathways": ["trauma", "stroke", "obstetric", "pediatric", "cardiac", "respiratory", "general"],
            "allowed_capabilities": [
                "icu",
                "oxygen",
                "ct",
                "surgical_team",
                "neonatal_support",
                "ventilator",
                "blood_bank",
                "isolation",
                "maternity",
                "pediatric",
            ],
            "allowed_specialists": [
                "emergency_physician",
                "surgeon",
                "neurosurgeon",
                "neurologist",
                "obstetrician",
                "pediatrician",
                "cardiologist",
                "anesthetist",
            ],
            "required_json_shape": {
                "acuity": "red|orange|yellow|green",
                "care_pathways": ["stroke"],
                "required_capabilities": ["ct", "icu", "oxygen"],
                "required_specialists": ["neurologist"],
                "summary": "one sentence ambulance summary",
                "rationale": "short clinical rationale",
                "confidence": 0.0,
                "source_model": self.model,
            },
            "patient": patient_json,
            "linked_patient_record": record_json,
            "scene_location": incident.scene_location.model_dump(mode="json"),
        }
        payload = await self._chat_json(system=system, user=json.dumps(user, ensure_ascii=False))
        payload["source_model"] = self.model
        payload = _normalize_triage_payload(payload)
        try:
            return TriageSignal.model_validate(payload)
        except ValidationError as exc:
            raise LLMResponseError(f"{self.provider_label} returned invalid triage JSON: {exc}") from exc

    async def generate_prealert(self, incident: Incident) -> str:
        await self.ensure_available()
        return await self._chat_text(
            system="You draft concise hospital emergency pre-alerts. Do not invent facts.",
            user=json.dumps(
                {
                    "task": "Write a concise hospital pre-alert for the receiving emergency team.",
                    "incident": incident.model_dump(mode="json"),
                    "format": "2-4 sentences. Include acuity, key vitals, suspected pathway, required prep, and ETA if available.",
                },
                ensure_ascii=False,
            ),
        )

    async def generate_handover(self, incident: Incident, request: HandoverRequest) -> str:
        await self.ensure_available()
        return await self._chat_text(
            system="You draft concise ambulance-to-hospital handover notes. Do not invent facts.",
            user=json.dumps(
                {
                    "task": "Write a structured digital handover note for ED intake.",
                    "incident": incident.model_dump(mode="json"),
                    "handover_updates": request.model_dump(mode="json"),
                    "format": "Use short labeled sections: Situation, Background, Assessment, Treatment, Requested readiness.",
                },
                ensure_ascii=False,
            ),
        )

    async def ensure_available(self) -> None:
        health = await self.health()
        if not health["available"]:
            detail = health.get("detail") or f"{self.provider_label} is not ready."
            raise LMStudioUnavailable(detail)

    async def _chat_json(self, system: str, user: str) -> dict[str, Any]:
        content = await self._chat(system=system, user=user, json_mode=True, tools=[_triage_tool()])
        try:
            return _parse_json_object(content)
        except json.JSONDecodeError:
            repaired = await self._repair_json(system=system, user=user, invalid_response=content)
            try:
                return _parse_json_object(repaired)
            except json.JSONDecodeError as exc:
                snippet = (repaired or content or "<empty response>").strip()[:500]
                raise LLMResponseError(f"{self.provider_label} did not return parseable JSON after repair: {snippet}") from exc

    async def _repair_json(self, system: str, user: str, invalid_response: str) -> str:
        repair_user = json.dumps(
            {
                "task": "Return one valid JSON object only. If the prior response was empty or malformed, regenerate the JSON from the original request.",
                "original_system_instruction": system,
                "original_request": user,
                "invalid_response": invalid_response,
            },
            ensure_ascii=False,
        )
        return await self._chat(
            system=(
                "You repair or regenerate malformed model output. Return one valid JSON object only. "
                "Do not include markdown, commentary, chain-of-thought, or analysis text. "
                "The first character of your response must be { and the final character must be }."
            ),
            user=repair_user,
            json_mode=True,
            tools=[_triage_tool()],
        )

    async def _chat_text(self, system: str, user: str) -> str:
        content = await self._chat(system=system, user=user, json_mode=False)
        cleaned = content.strip()
        if not cleaned:
            raise LLMResponseError(f"{self.provider_label} returned an empty response.")
        return cleaned

    async def _chat(self, system: str, user: str, json_mode: bool, tools: list[dict[str, Any]] | None = None) -> str:
        if json_mode:
            system = f"{system}\nJSON-only mode is mandatory. Do not explain. Do not think step by step."
            user = f"/no_think\n{user}\nReturn only the JSON object. Start with {{ and end with }}."
        max_tokens = 1400 if json_mode else 350
        if self.provider == "nvidia_nim" and json_mode:
            max_tokens = 700
        kwargs: dict[str, Any] = {
            "model": self.resolved_model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "max_tokens": max_tokens,
            "temperature": 0.1,
        }
        if self.provider == "lmstudio":
            kwargs["extra_body"] = {
                "chat_template_kwargs": {
                    "enable_thinking": False,
                },
            }
        if tools and self.provider == "lmstudio":
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "required"

        response = await self._create_chat_completion(kwargs)

        message = response.choices[0].message
        return _message_text(message)

    async def _create_chat_completion(self, kwargs: dict[str, Any]) -> Any:
        if self.provider == "nvidia_nim":
            return await self._create_nvidia_nim_chat_completion(kwargs)

        attempts = _chat_request_attempts(kwargs)
        last_bad_request: BadRequestError | None = None
        for attempt in attempts:
            try:
                return await self.client.chat.completions.create(**attempt)
            except BadRequestError as exc:
                if _looks_unavailable(exc):
                    raise LMStudioUnavailable(f"{self.provider_label} unavailable: {exc}") from exc
                last_bad_request = exc
            except (APIConnectionError, APITimeoutError) as exc:
                raise LMStudioUnavailable(f"{self.provider_label} unavailable: {exc}") from exc
            except APIError as exc:
                if _looks_unavailable(exc):
                    raise LMStudioUnavailable(f"{self.provider_label} unavailable: {exc}") from exc
                raise LLMResponseError(f"{self.provider_label} API error: {exc}") from exc

        assert last_bad_request is not None
        raise LLMResponseError(f"{self.provider_label} request was rejected: {last_bad_request}") from last_bad_request

    async def _create_nvidia_nim_chat_completion(self, kwargs: dict[str, Any]) -> Any:
        attempts = _chat_request_attempts(kwargs)
        last_error: str | None = None
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=self.settings.llm_timeout_seconds) as client:
            for attempt in attempts:
                payload = _nvidia_nim_payload(attempt)
                try:
                    response = await client.post(f"{self.base_url}/chat/completions", headers=headers, json=payload)
                except httpx.TimeoutException as exc:
                    raise LMStudioUnavailable(f"{self.provider_label} unavailable: {exc}") from exc
                except httpx.HTTPError as exc:
                    raise LMStudioUnavailable(f"{self.provider_label} unavailable: {exc}") from exc

                if response.status_code in {401, 403}:
                    raise LMStudioUnavailable(f"{self.provider_label} authentication failed.")
                if response.status_code == 400 and ("tools" in payload or "tool_choice" in payload):
                    last_error = response.text[:500]
                    continue
                if response.status_code >= 400:
                    raise LLMResponseError(f"{self.provider_label} request failed with HTTP {response.status_code}: {response.text[:500]}")

                body = response.json()
                message = body["choices"][0]["message"]
                return SimpleNamespace(
                    choices=[
                        SimpleNamespace(
                            message=SimpleNamespace(
                                content=message.get("content") or "",
                                tool_calls=message.get("tool_calls"),
                            )
                        )
                    ]
                )

        raise LLMResponseError(f"{self.provider_label} request was rejected: {last_error or 'unknown error'}")


def _provider_label(provider: str) -> str:
    return {
        "lmstudio": "LM Studio",
        "nvidia_nim": "NVIDIA NIM",
    }.get(provider, provider)


def _provider_base_url(settings: Settings) -> str:
    if settings.llm_provider == "nvidia_nim":
        return settings.nvidia_nim_base_url
    return settings.lmstudio_base_url


def _provider_model(settings: Settings) -> str:
    if settings.llm_provider == "nvidia_nim":
        return settings.nvidia_nim_model
    return settings.lmstudio_model


def _provider_api_key(settings: Settings) -> str:
    if settings.llm_provider == "nvidia_nim":
        return settings.nvidia_nim_api_key or "not-used"
    return "lm-studio"


def _hosted_nvidia_nim(base_url: str) -> bool:
    return "integrate.api.nvidia.com" in base_url.lower()


def _auth_headers(api_key: str | None) -> dict[str, str]:
    if not api_key or api_key == "not-used":
        return {}
    return {"Authorization": f"Bearer {api_key}"}


def _chat_request_attempts(kwargs: dict[str, Any]) -> list[dict[str, Any]]:
    attempts: list[dict[str, Any]] = []

    def add(candidate: dict[str, Any]) -> None:
        if candidate not in attempts:
            attempts.append(candidate)

    add(dict(kwargs))
    if "extra_body" in kwargs:
        without_extra = dict(kwargs)
        without_extra.pop("extra_body", None)
        add(without_extra)
    if "tools" in kwargs or "tool_choice" in kwargs:
        without_tools = dict(kwargs)
        without_tools.pop("extra_body", None)
        without_tools.pop("tools", None)
        without_tools.pop("tool_choice", None)
        add(without_tools)
    return attempts


def _nvidia_nim_payload(kwargs: dict[str, Any]) -> dict[str, Any]:
    allowed_keys = {"model", "messages", "max_tokens", "temperature", "tools", "tool_choice"}
    return {key: value for key, value in kwargs.items() if key in allowed_keys}


def _message_text(message: Any) -> str:
    parts: list[str] = []
    content = getattr(message, "content", None)
    _append_content(parts, content)
    _append_tool_calls(parts, getattr(message, "tool_calls", None))

    if hasattr(message, "model_dump"):
        dumped = message.model_dump()
        for key in ["reasoning_content", "reasoning", "thinking", "response", "text"]:
            _append_content(parts, dumped.get(key))
        _append_tool_calls(parts, dumped.get("tool_calls"))
        extra = dumped.get("model_extra")
        if isinstance(extra, dict):
            for key in ["reasoning_content", "reasoning", "thinking", "response", "text"]:
                _append_content(parts, extra.get(key))
            _append_tool_calls(parts, extra.get("tool_calls"))

    model_extra = getattr(message, "model_extra", None)
    if isinstance(model_extra, dict):
        for key in ["reasoning_content", "reasoning", "thinking", "response", "text"]:
            _append_content(parts, model_extra.get(key))
        _append_tool_calls(parts, model_extra.get("tool_calls"))

    return "\n".join(part for part in parts if part).strip()


def _append_tool_calls(parts: list[str], tool_calls: Any) -> None:
    if not tool_calls:
        return
    for tool_call in tool_calls:
        function = tool_call.get("function") if isinstance(tool_call, dict) else getattr(tool_call, "function", None)
        if not function:
            continue
        arguments = function.get("arguments") if isinstance(function, dict) else getattr(function, "arguments", None)
        _append_content(parts, arguments)


def _append_content(parts: list[str], content: Any) -> None:
    if content is None:
        return
    if isinstance(content, str):
        if content.strip():
            parts.append(content)
        return
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict):
                _append_content(parts, item.get("text") or item.get("content"))
            else:
                _append_content(parts, item)
        return
    if isinstance(content, dict):
        _append_content(parts, content.get("text") or content.get("content"))
        return
    text = str(content).strip()
    if text:
        parts.append(text)


def _parse_json_object(content: str) -> dict[str, Any]:
    if not content.strip():
        raise json.JSONDecodeError("empty response", content, 0)

    tool_payload = _parse_tool_call_parameters(content)
    if tool_payload:
        return tool_payload

    decoder = json.JSONDecoder()
    stripped = _remove_fence_markers(content)
    for index, char in enumerate(stripped):
        if char != "{":
            continue
        try:
            parsed, _ = decoder.raw_decode(stripped[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    raise json.JSONDecodeError("no JSON object found", stripped, 0)


def _parse_tool_call_parameters(content: str) -> dict[str, Any]:
    matches = re.findall(r"<parameter=([^>]+)>\s*(.*?)\s*</parameter>", content, flags=re.DOTALL | re.IGNORECASE)
    payload: dict[str, Any] = {}
    for key, raw_value in matches:
        clean_key = key.strip()
        clean_value = raw_value.strip()
        if not clean_key:
            continue
        payload[clean_key] = _parse_tool_value(clean_value)
    return payload


def _parse_tool_value(value: str) -> Any:
    if not value:
        return value
    if value[0] in "[{\"" or value.lower() in {"true", "false", "null"}:
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            pass
    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        return value


def _remove_fence_markers(content: str) -> str:
    return (
        content.replace("```json", "")
        .replace("```JSON", "")
        .replace("```", "")
        .replace("<json>", "")
        .replace("</json>", "")
    )


def _looks_unavailable(exc: Exception) -> bool:
    message = str(exc).lower()
    return any(fragment in message for fragment in ["unloaded", "not-loaded", "not loaded", "connection", "timed out"])


def _model_aliases(model: str) -> set[str]:
    aliases = {model}
    if "/" in model:
        aliases.add(model.rsplit("/", 1)[-1])
    return aliases


def _triage_tool() -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": "submit_triage",
            "description": "Submit structured ambulance triage decision-support data.",
            "parameters": {
                "type": "object",
                "properties": {
                    "acuity": {"type": "string"},
                    "care_pathways": {"type": "array", "items": {"type": "string"}},
                    "required_capabilities": {"type": "array", "items": {"type": "string"}},
                    "required_specialists": {"type": "array", "items": {"type": "string"}},
                    "summary": {"type": "string"},
                    "rationale": {"type": "string"},
                    "confidence": {"type": "number"},
                },
                "required": [
                    "acuity",
                    "care_pathways",
                    "required_capabilities",
                    "required_specialists",
                    "summary",
                    "rationale",
                    "confidence",
                ],
            },
        },
    }


def _normalize_triage_payload(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    normalized["acuity"] = _normalize_acuity(str(normalized.get("acuity", "orange")))
    normalized["care_pathways"] = _normalize_list(normalized.get("care_pathways"), _normalize_pathway)
    normalized["required_capabilities"] = _normalize_list(normalized.get("required_capabilities"), _normalize_capability)
    normalized["required_specialists"] = _normalize_list(normalized.get("required_specialists"), _normalize_specialist)
    normalized["confidence"] = _normalize_confidence(normalized.get("confidence", 0.7))
    return normalized


def _normalize_list(value: Any, normalizer) -> list[str]:
    if value is None:
        return []
    raw_items = value if isinstance(value, list) else [value]
    items = []
    for item in raw_items:
        normalized = normalizer(str(item))
        if normalized and normalized not in items:
            items.append(normalized)
    return items


def _normalize_acuity(value: str) -> str:
    lower = value.lower()
    if any(token in lower for token in ["red", "critical", "emergency", "high", "urgent", "severe"]):
        return "red"
    if any(token in lower for token in ["orange", "moderate"]):
        return "orange"
    if any(token in lower for token in ["green", "low", "minor"]):
        return "green"
    return "yellow"


def _normalize_pathway(value: str) -> str:
    lower = value.lower()
    if "stroke" in lower or "neuro" in lower:
        return "stroke"
    if "trauma" in lower or "surgery" in lower:
        return "trauma"
    if "obstetric" in lower or "matern" in lower or "pregnan" in lower:
        return "obstetric"
    if "pediatric" in lower or "child" in lower:
        return "pediatric"
    if "cardiac" in lower or "chest" in lower:
        return "cardiac"
    if "respir" in lower or "oxygen" in lower or "asthma" in lower:
        return "respiratory"
    return "general"


def _normalize_capability(value: str) -> str:
    lower = value.lower()
    if "ct" in lower or "imaging" in lower or "scan" in lower:
        return "ct"
    if "icu" in lower or "intensive" in lower:
        return "icu"
    if "oxygen" in lower or "airway" in lower:
        return "oxygen"
    if "ventilator" in lower or "ventilation" in lower:
        return "ventilator"
    if "surg" in lower or "operating" in lower or "theatre" in lower:
        return "surgical_team"
    if "neonatal" in lower or "nicu" in lower:
        return "neonatal_support"
    if "blood" in lower:
        return "blood_bank"
    if "matern" in lower or "obstetric" in lower:
        return "maternity"
    if "pediatric" in lower or "paediatric" in lower:
        return "pediatric"
    if "isolation" in lower:
        return "isolation"
    return value.strip().lower().replace(" ", "_").replace("-", "_")


def _normalize_specialist(value: str) -> str:
    lower = value.lower()
    if "neuro" in lower or "stroke" in lower:
        return "neurologist"
    if "emergency" in lower or "ed " in lower:
        return "emergency_physician"
    if "surgeon" in lower or "surgical" in lower:
        return "surgeon"
    if "obstetric" in lower or "matern" in lower:
        return "obstetrician"
    if "pediatric" in lower or "paediatric" in lower:
        return "pediatrician"
    if "cardio" in lower:
        return "cardiologist"
    if "anesth" in lower or "anaesth" in lower:
        return "anesthetist"
    return value.strip().lower().replace(" ", "_").replace("-", "_")


def _normalize_confidence(value: Any) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return 0.7
    if confidence > 1:
        confidence = confidence / 100
    return max(0.0, min(1.0, confidence))
