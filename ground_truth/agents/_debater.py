from pydantic import BaseModel, Field

from ground_truth.llm import load_prompt, structured_call
from ground_truth.models import Argument, Claim, Evidence, Stance
from ground_truth.search import search as web_search

_REFUTE_QUERY_PROMPT = (
    "Generate 2-3 web search queries most likely to surface evidence that REFUTES, "
    'debunks, or contradicts this claim (e.g. append terms like "debunked", "false", '
    '"criticism of", "fact check").\n\nClaim: {claim}'
)
_SUPPORT_QUERY_PROMPT = (
    "Generate 2-3 web search queries most likely to surface evidence that CONFIRMS or "
    'supports this claim (e.g. append terms like "confirmed", "evidence for", "study").'
    "\n\nClaim: {claim}"
)


class _SearchQueries(BaseModel):
    queries: list[str] = Field(min_length=1, max_length=3)


class _ArgumentDraft(BaseModel):
    reasoning: str
    strength: float = Field(ge=0, le=1)
    used_evidence_indices: list[int] = Field(default_factory=list)


def _generate_queries(claim: Claim, stance: Stance) -> list[str]:
    template = _REFUTE_QUERY_PROMPT if stance == Stance.REFUTE else _SUPPORT_QUERY_PROMPT
    result = structured_call(template.format(claim=claim.text), _SearchQueries)
    return result.queries[:3]


def _gather_evidence(queries: list[str]) -> list[Evidence]:
    evidence: list[Evidence] = []
    seen_urls: set[str] = set()
    for query in queries:
        for item in web_search(query):
            if item.url not in seen_urls:
                seen_urls.add(item.url)
                evidence.append(item)
    return evidence


def run_debate_side(
    claim: Claim,
    stance: Stance,
    argument_prompt_name: str,
    opponent_argument: Argument | None = None,
) -> Argument:
    queries = _generate_queries(claim, stance)
    evidence = _gather_evidence(queries)

    evidence_block = (
        "\n".join(
            f"[{i}] {e.title} ({e.source_domain}, credibility {e.credibility}): "
            f"{e.snippet} — {e.url}"
            for i, e in enumerate(evidence)
        )
        or "(no search results found)"
    )
    opponent_block = (
        f"Stance: {opponent_argument.stance.value}, reasoning: {opponent_argument.reasoning}"
        if opponent_argument
        else "(not available — this is round 1, independent research only)"
    )

    prompt = load_prompt(argument_prompt_name).format(
        claim=claim.text,
        evidence=evidence_block,
        opponent_argument=opponent_block,
    )
    draft = structured_call(prompt, _ArgumentDraft)

    used = [evidence[i] for i in draft.used_evidence_indices if 0 <= i < len(evidence)]
    return Argument(
        stance=stance,
        reasoning=draft.reasoning,
        evidence=used,
        strength=draft.strength,
    )
