import json
import re
from typing import TypeVar

from pydantic import BaseModel, ValidationError
from tenacity import retry, stop_after_attempt, wait_exponential

from ground_truth import config

T = TypeVar("T", bound=BaseModel)

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


class LLMError(RuntimeError):
    """Raised when the LLM fails to produce output matching the requested schema."""


def load_prompt(name: str) -> str:
    path = config.PROMPTS_DIR / f"{name}.md"
    return path.read_text(encoding="utf-8")


def _strip_fences(text: str) -> str:
    return _FENCE_RE.sub("", text.strip()).strip()


def _extract_json(text: str) -> str:
    cleaned = _strip_fences(text)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end < start:
        start = cleaned.find("[")
        end = cleaned.rfind("]")
    if start == -1 or end == -1 or end < start:
        return cleaned
    return cleaned[start : end + 1]


def _chat(messages: list[dict], model: str, temperature: float) -> str:
    import litellm

    config.ensure_llm_env()
    response = litellm.completion(model=model, messages=messages, temperature=temperature)
    return response["choices"][0]["message"]["content"]


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
def _chat_with_retry(messages: list[dict], model: str, temperature: float) -> str:
    return _chat(messages, model, temperature)


def structured_call(
    prompt: str,
    schema: type[T],
    model: str | None = None,
    temperature: float = 0.2,
) -> T:
    """Call the LLM and parse its response into `schema`, repairing malformed JSON."""
    model = model or config.select_model()
    schema_json = json.dumps(schema.model_json_schema())
    full_prompt = (
        f"{prompt}\n\n"
        "Respond with ONLY valid JSON matching this schema, no markdown code fences, "
        f"no commentary before or after the JSON:\n{schema_json}"
    )
    messages = [{"role": "user", "content": full_prompt}]

    last_error: Exception | None = None
    raw_output = ""
    for attempt in range(config.LLM_MAX_REPAIR_ATTEMPTS + 1):
        raw_output = _chat_with_retry(messages, model, temperature)
        try:
            data = json.loads(_extract_json(raw_output))
            return schema.model_validate(data)
        except (json.JSONDecodeError, ValidationError) as exc:
            last_error = exc
            messages = [
                {"role": "user", "content": full_prompt},
                {"role": "assistant", "content": raw_output},
                {
                    "role": "user",
                    "content": (
                        "That was not valid JSON matching the schema. "
                        f"Error: {exc}\n"
                        "Return ONLY the corrected JSON, no commentary, no code fences."
                    ),
                },
            ]

    raise LLMError(
        f"LLM failed to produce valid {schema.__name__} JSON after "
        f"{config.LLM_MAX_REPAIR_ATTEMPTS + 1} attempts: {last_error}\nLast output: {raw_output}"
    )
