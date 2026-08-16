import json
import re
import threading
import time
from collections import deque
from typing import TypeVar

from pydantic import BaseModel, ValidationError
from tenacity import retry, stop_after_attempt, wait_exponential

from ground_truth import config

T = TypeVar("T", bound=BaseModel)

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


class LLMError(RuntimeError):
    """Raised when the LLM fails to produce output matching the requested schema."""


class _RateLimiter:
    """Sliding-window limiter shared by every LLM call. Claims audit concurrently
    (see graph.py's Send fan-out), so without this a text with just a couple of
    claims bursts well past a free-tier requests-per-minute quota in seconds."""

    def __init__(self, max_calls: int, period_seconds: float):
        self.max_calls = max_calls
        self.period = period_seconds
        self._lock = threading.Lock()
        self._calls: deque[float] = deque()

    def acquire(self) -> None:
        while True:
            with self._lock:
                now = time.monotonic()
                while self._calls and now - self._calls[0] > self.period:
                    self._calls.popleft()
                if len(self._calls) < self.max_calls:
                    self._calls.append(now)
                    return
                sleep_for = self.period - (now - self._calls[0]) + 0.05
            time.sleep(sleep_for)


_rate_limiter = _RateLimiter(config.LLM_MAX_CALLS_PER_MINUTE, 60.0)


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
    _rate_limiter.acquire()
    response = litellm.completion(model=model, messages=messages, temperature=temperature)
    return response["choices"][0]["message"]["content"]


@retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=2, min=2, max=30))
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
