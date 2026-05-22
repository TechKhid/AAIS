from __future__ import annotations

from types import SimpleNamespace

from app.config import Settings, _normalize_llm_provider
from app.services.llm_client import LMStudioClient, _message_text, _model_aliases, _normalize_triage_payload, _parse_json_object


def test_parse_json_object_from_markdown_and_extra_text():
    content = """
    I will return the object now.
    ```json
    {"acuity":"red","care_pathways":["stroke"]}
    ```
    """

    parsed = _parse_json_object(content)

    assert parsed["acuity"] == "red"
    assert parsed["care_pathways"] == ["stroke"]


def test_message_text_reads_lmstudio_extra_fields():
    message = SimpleNamespace(
        content="",
        model_extra={
            "reasoning_content": "",
            "text": '{"acuity":"orange","care_pathways":["respiratory"]}',
        },
    )

    assert "respiratory" in _message_text(message)


def test_message_text_reads_openai_tool_call_arguments():
    message = SimpleNamespace(
        content="",
        tool_calls=[
            SimpleNamespace(
                function=SimpleNamespace(
                    arguments='{"acuity":"red","care_pathways":["trauma"]}',
                ),
            )
        ],
    )

    assert "trauma" in _message_text(message)


def test_model_aliases_accept_lmstudio_short_name():
    assert _model_aliases("qwen/qwen3.5-4b") == {"qwen/qwen3.5-4b", "qwen3.5-4b"}


def test_provider_aliases_accept_nvidia_nim_names():
    assert _normalize_llm_provider("nim") == "nvidia_nim"
    assert _normalize_llm_provider("nvidia-nim") == "nvidia_nim"


def test_nvidia_nim_client_uses_nim_connection_settings():
    settings = Settings(
        llm_provider="nvidia_nim",
        nvidia_nim_base_url="https://integrate.api.nvidia.com/v1",
        nvidia_nim_model="meta/llama-3.1-8b-instruct",
        nvidia_nim_api_key="test-key",
    )

    client = LMStudioClient(settings)

    assert client.provider == "nvidia_nim"
    assert client.base_url == "https://integrate.api.nvidia.com/v1"
    assert client.model == "meta/llama-3.1-8b-instruct"
    assert client.api_key == "test-key"


def test_parse_lmstudio_tool_call_from_reasoning_content():
    content = """
    <tool_call>
    <function=submit_triage>
    <parameter=acuity>
    high
    </parameter>
    <parameter=care_pathways>
    ["emergency department", "stroke unit"]
    </parameter>
    <parameter=required_capabilities>
    ["CT scan", "oxygen"]
    </parameter>
    <parameter=required_specialists>
    ["Stroke Specialist"]
    </parameter>
    <parameter=summary>
    Suspected stroke.
    </parameter>
    <parameter=rationale>
    Time-sensitive focal deficit.
    </parameter>
    <parameter=confidence>
    0.9
    </parameter>
    </function>
    </tool_call>
    """

    parsed = _normalize_triage_payload(_parse_json_object(content))

    assert parsed["acuity"] == "red"
    assert parsed["care_pathways"] == ["general", "stroke"]
    assert parsed["required_capabilities"] == ["ct", "oxygen"]
    assert parsed["required_specialists"] == ["neurologist"]
