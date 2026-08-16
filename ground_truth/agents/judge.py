from typing import Literal

from pydantic import BaseModel, Field, field_validator

from ground_truth.llm import load_prompt, structured_call
from ground_truth.models import Argument, Claim, Evidence, Verdict


class _VerdictDraft(BaseModel):
    confidence: int = Field(ge=0, le=100)
    label: Literal["supported", "disputed", "contradicted", "unverifiable"]
    reasoning: str
    dissent: str
    key_citation_indices: list[int] = Field(default_factory=list)

    @field_validator("dissent")
    @classmethod
    def dissent_must_not_be_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError(
                "dissent must not be empty — state the strongest surviving point "
                "from the side you ruled against"
            )
        return v


def _combined_evidence_pool(prosecution: Argument, defense: Argument) -> list[Evidence]:
    pool: list[Evidence] = []
    seen_urls: set[str] = set()
    for item in [*prosecution.evidence, *defense.evidence]:
        if item.url not in seen_urls:
            seen_urls.add(item.url)
            pool.append(item)
    return pool


def judge(claim: Claim, prosecution: Argument, defense: Argument) -> Verdict:
    pool = _combined_evidence_pool(prosecution, defense)
    evidence_block = (
        "\n".join(
            f"[{i}] {e.title} ({e.source_domain}, credibility {e.credibility}): "
            f"{e.snippet} — {e.url}"
            for i, e in enumerate(pool)
        )
        or "(no evidence found by either side)"
    )

    prompt = load_prompt("judge").format(
        claim=claim.text,
        prosecution_strength=prosecution.strength,
        prosecution_reasoning=prosecution.reasoning,
        defense_strength=defense.strength,
        defense_reasoning=defense.reasoning,
        evidence=evidence_block,
    )
    draft = structured_call(prompt, _VerdictDraft)

    citations = [pool[i] for i in draft.key_citation_indices if 0 <= i < len(pool)]
    return Verdict(
        claim_id=claim.id,
        confidence=draft.confidence,
        label=draft.label,
        reasoning=draft.reasoning,
        key_citations=citations,
        dissent=draft.dissent,
    )
