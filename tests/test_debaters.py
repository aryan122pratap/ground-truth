from ground_truth.agents import _debater, defender, prosecutor
from ground_truth.models import Claim, Evidence, Stance


def make_claim() -> Claim:
    return Claim(
        id="c1",
        text="SpaceX launched 90 missions in 2023.",
        original_sentence="SpaceX launched 90 missions in 2023.",
        checkable=True,
        claim_type="statistical",
    )


def test_prosecute_builds_argument_from_evidence(monkeypatch):
    monkeypatch.setattr(_debater, "_generate_queries", lambda claim, stance: ["q1", "q2"])
    monkeypatch.setattr(
        _debater,
        "_gather_evidence",
        lambda queries: [
            Evidence(url="https://x.com/a", title="t1", snippet="s1", source_domain="x.com"),
            Evidence(url="https://y.com/b", title="t2", snippet="s2", source_domain="y.com"),
        ],
    )
    monkeypatch.setattr(
        _debater,
        "structured_call",
        lambda prompt, schema: schema.model_validate(
            {"reasoning": "Found contradicting data.", "strength": 0.8, "used_evidence_indices": [1]}
        ),
    )

    arg = prosecutor.prosecute(make_claim())

    assert arg.stance == Stance.REFUTE
    assert arg.strength == 0.8
    assert len(arg.evidence) == 1
    assert arg.evidence[0].url == "https://y.com/b"


def test_defend_honesty_clause_no_evidence(monkeypatch):
    monkeypatch.setattr(_debater, "_generate_queries", lambda claim, stance: ["q1"])
    monkeypatch.setattr(_debater, "_gather_evidence", lambda queries: [])
    monkeypatch.setattr(
        _debater,
        "structured_call",
        lambda prompt, schema: schema.model_validate(
            {"reasoning": "No supporting evidence found.", "strength": 0.1, "used_evidence_indices": []}
        ),
    )

    arg = defender.defend(make_claim())

    assert arg.stance == Stance.SUPPORT
    assert arg.strength < 0.3
    assert arg.evidence == []


def test_prosecute_out_of_range_indices_are_dropped(monkeypatch):
    monkeypatch.setattr(_debater, "_generate_queries", lambda claim, stance: ["q1"])
    monkeypatch.setattr(
        _debater,
        "_gather_evidence",
        lambda queries: [Evidence(url="https://x.com/a", title="t", snippet="s", source_domain="x.com")],
    )
    monkeypatch.setattr(
        _debater,
        "structured_call",
        lambda prompt, schema: schema.model_validate(
            {"reasoning": "r", "strength": 0.5, "used_evidence_indices": [5, -1]}
        ),
    )

    arg = prosecutor.prosecute(make_claim())
    assert arg.evidence == []
