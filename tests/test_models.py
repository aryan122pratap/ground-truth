import pytest
from pydantic import ValidationError

from ground_truth.models import (
    Argument,
    AuditResult,
    Claim,
    Evidence,
    Stance,
    Verdict,
)


def make_evidence(**overrides) -> Evidence:
    defaults = dict(
        url="https://example.gov/report",
        title="A report",
        snippet="Some snippet text.",
        source_domain="example.gov",
    )
    defaults.update(overrides)
    return Evidence(**defaults)


def test_evidence_defaults():
    e = make_evidence()
    assert e.credibility == 0.5
    assert e.published is None


def test_evidence_credibility_bounds():
    with pytest.raises(ValidationError):
        make_evidence(credibility=1.5)
    with pytest.raises(ValidationError):
        make_evidence(credibility=-0.1)


def test_claim_roundtrip():
    c = Claim(
        id="c1",
        text="Elon Musk founded SpaceX in 2002.",
        original_sentence="He founded it in 2002.",
        checkable=True,
        claim_type="factual",
    )
    assert c.checkable is True
    assert c.claim_type == "factual"


def test_claim_invalid_claim_type():
    with pytest.raises(ValidationError):
        Claim(
            id="c1",
            text="x",
            original_sentence="x",
            checkable=True,
            claim_type="not_a_real_type",
        )


def test_argument_strength_bounds():
    with pytest.raises(ValidationError):
        Argument(stance=Stance.SUPPORT, reasoning="r", evidence=[], strength=1.1)
    a = Argument(stance=Stance.REFUTE, reasoning="r", evidence=[make_evidence()], strength=0.7)
    assert a.stance == Stance.REFUTE


def test_verdict_requires_nonempty_dissent():
    with pytest.raises(ValidationError):
        Verdict(
            claim_id="c1",
            confidence=80,
            label="supported",
            reasoning="r",
            key_citations=[make_evidence()],
            dissent="",
        )
    with pytest.raises(ValidationError):
        Verdict(
            claim_id="c1",
            confidence=80,
            label="supported",
            reasoning="r",
            key_citations=[make_evidence()],
            dissent="   ",
        )


def test_verdict_confidence_bounds():
    with pytest.raises(ValidationError):
        Verdict(
            claim_id="c1",
            confidence=101,
            label="supported",
            reasoning="r",
            key_citations=[],
            dissent="valid dissent",
        )


def test_verdict_valid():
    v = Verdict(
        claim_id="c1",
        confidence=72,
        label="supported",
        reasoning="Strong evidence from a .gov source.",
        key_citations=[make_evidence()],
        dissent="The date is disputed by one blog post.",
    )
    assert v.label == "supported"


def test_audit_result_roundtrip():
    claim = Claim(
        id="c1",
        text="x",
        original_sentence="x",
        checkable=True,
        claim_type="factual",
    )
    arg = Argument(stance=Stance.SUPPORT, reasoning="r", evidence=[], strength=0.5)
    verdict = Verdict(
        claim_id="c1",
        confidence=50,
        label="unverifiable",
        reasoning="No sources found.",
        key_citations=[],
        dissent="No counter-evidence found either.",
    )
    result = AuditResult(
        original_text="x",
        claims=[claim],
        arguments={"c1": [arg]},
        verdicts=[verdict],
        elapsed_seconds=1.23,
        model_used="gemini/gemini-2.0-flash",
    )
    assert result.verdicts[0].claim_id == "c1"
    dumped = result.model_dump()
    assert dumped["model_used"] == "gemini/gemini-2.0-flash"
