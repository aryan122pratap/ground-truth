import pytest
from pydantic import ValidationError

from ground_truth.agents import judge as judge_module
from ground_truth.models import Argument, Claim, Evidence, Stance


def make_claim() -> Claim:
    return Claim(
        id="c1",
        text="SpaceX launched 90 missions in 2023.",
        original_sentence="SpaceX launched 90 missions in 2023.",
        checkable=True,
        claim_type="statistical",
    )


def make_evidence(url: str, credibility: float = 0.8) -> Evidence:
    return Evidence(url=url, title="t", snippet="s", source_domain="d.com", credibility=credibility)


def test_judge_produces_valid_verdict_with_citations(monkeypatch):
    prosecution = Argument(stance=Stance.REFUTE, reasoning="weak case", evidence=[], strength=0.2)
    defense = Argument(
        stance=Stance.SUPPORT,
        reasoning="strong case",
        evidence=[make_evidence("https://nasa.gov/x")],
        strength=0.9,
    )

    monkeypatch.setattr(
        judge_module,
        "structured_call",
        lambda prompt, schema: schema.model_validate(
            {
                "confidence": 85,
                "label": "supported",
                "reasoning": "NASA source confirms it.",
                "dissent": "Prosecution found no counter-evidence, only asserted skepticism.",
                "key_citation_indices": [0],
            }
        ),
    )

    verdict = judge_module.judge(make_claim(), prosecution, defense)

    assert verdict.claim_id == "c1"
    assert verdict.confidence == 85
    assert verdict.label == "supported"
    assert len(verdict.key_citations) == 1
    assert verdict.key_citations[0].url == "https://nasa.gov/x"


def test_judge_deduplicates_evidence_pool_by_url(monkeypatch):
    shared_url = "https://shared.com/x"
    prosecution = Argument(
        stance=Stance.REFUTE, reasoning="r", evidence=[make_evidence(shared_url)], strength=0.5
    )
    defense = Argument(
        stance=Stance.SUPPORT, reasoning="r", evidence=[make_evidence(shared_url)], strength=0.5
    )

    captured = {}

    def fake_structured_call(prompt, schema):
        captured["prompt"] = prompt
        return schema.model_validate(
            {
                "confidence": 50,
                "label": "disputed",
                "reasoning": "conflicting",
                "dissent": "the other side has a point too",
                "key_citation_indices": [0],
            }
        )

    monkeypatch.setattr(judge_module, "structured_call", fake_structured_call)
    verdict = judge_module.judge(make_claim(), prosecution, defense)
    assert captured["prompt"].count(shared_url) == 1
    assert len(verdict.key_citations) == 1


def test_judge_raises_when_llm_omits_dissent(monkeypatch):
    prosecution = Argument(stance=Stance.REFUTE, reasoning="r", evidence=[], strength=0.5)
    defense = Argument(stance=Stance.SUPPORT, reasoning="r", evidence=[], strength=0.5)

    monkeypatch.setattr(
        judge_module,
        "structured_call",
        lambda prompt, schema: schema.model_validate(
            {
                "confidence": 50,
                "label": "unverifiable",
                "reasoning": "no evidence",
                "dissent": "",
                "key_citation_indices": [],
            }
        ),
    )

    with pytest.raises(ValidationError):
        judge_module.judge(make_claim(), prosecution, defense)
