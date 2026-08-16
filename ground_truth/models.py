from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class Stance(str, Enum):
    SUPPORT = "support"
    REFUTE = "refute"


class Evidence(BaseModel):
    url: str
    title: str
    snippet: str
    source_domain: str
    published: str | None = None
    credibility: float = Field(ge=0, le=1, default=0.5)


class Claim(BaseModel):
    id: str
    text: str
    original_sentence: str
    checkable: bool
    claim_type: Literal["factual", "statistical", "causal", "opinion", "prediction"]


class Argument(BaseModel):
    stance: Stance
    reasoning: str
    evidence: list[Evidence]
    strength: float = Field(ge=0, le=1)


class Verdict(BaseModel):
    claim_id: str
    confidence: int = Field(ge=0, le=100)
    label: Literal["supported", "disputed", "contradicted", "unverifiable"]
    reasoning: str
    key_citations: list[Evidence]
    dissent: str

    @field_validator("dissent")
    @classmethod
    def dissent_must_not_be_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("dissent must not be empty — the judge must always state the strongest surviving counter-argument")
        return v


class AuditResult(BaseModel):
    original_text: str
    claims: list[Claim]
    arguments: dict[str, list[Argument]]
    verdicts: list[Verdict]
    elapsed_seconds: float
    model_used: str
