import pytest
from pydantic import BaseModel

from ground_truth import llm


class Dummy(BaseModel):
    value: int
    label: str


def _fake_response(content: str) -> dict:
    return {"choices": [{"message": {"content": content}}]}


def test_structured_call_parses_clean_json(monkeypatch):
    monkeypatch.setattr(
        llm, "_chat_with_retry", lambda messages, model, temperature: '{"value": 3, "label": "ok"}'
    )
    result = llm.structured_call("prompt", Dummy, model="fake-model")
    assert result == Dummy(value=3, label="ok")


def test_structured_call_strips_markdown_fences(monkeypatch):
    monkeypatch.setattr(
        llm,
        "_chat_with_retry",
        lambda messages, model, temperature: '```json\n{"value": 7, "label": "fenced"}\n```',
    )
    result = llm.structured_call("prompt", Dummy, model="fake-model")
    assert result.value == 7


def test_structured_call_repairs_malformed_json_then_succeeds(monkeypatch):
    calls = {"n": 0}

    def fake_chat(messages, model, temperature):
        calls["n"] += 1
        if calls["n"] == 1:
            return "not json at all"
        return '{"value": 1, "label": "repaired"}'

    monkeypatch.setattr(llm, "_chat_with_retry", fake_chat)
    result = llm.structured_call("prompt", Dummy, model="fake-model")
    assert result.label == "repaired"
    assert calls["n"] == 2


def test_structured_call_raises_llm_error_after_exhausting_repairs(monkeypatch):
    monkeypatch.setattr(llm, "_chat_with_retry", lambda messages, model, temperature: "still not json")
    with pytest.raises(llm.LLMError):
        llm.structured_call("prompt", Dummy, model="fake-model")
