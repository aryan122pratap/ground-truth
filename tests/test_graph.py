from ground_truth import graph as graph_module
from ground_truth.models import Argument, Claim, Stance, Verdict


def make_claim(id_="c1", checkable=True, claim_type="factual") -> Claim:
    return Claim(
        id=id_,
        text=f"Claim {id_} text.",
        original_sentence=f"Claim {id_} text.",
        checkable=checkable,
        claim_type=claim_type,
    )


def make_verdict(claim_id, confidence, label="supported") -> Verdict:
    return Verdict(
        claim_id=claim_id,
        confidence=confidence,
        label=label,
        reasoning="r",
        key_citations=[],
        dissent="the strongest counter-point",
    )


def _arg(stance, strength=0.7):
    return Argument(stance=stance, reasoning="r", evidence=[], strength=strength)


def test_run_audit_skips_when_no_checkable_claims(monkeypatch):
    monkeypatch.setattr(
        graph_module.extractor,
        "extract_claims",
        lambda text: [make_claim(checkable=False, claim_type="opinion")],
    )
    graph_module._compiled_graph = None
    result = graph_module.run_audit("just an opinion")
    assert result.verdicts == []
    assert len(result.claims) == 1


def test_run_audit_single_claim_no_rebuttal(monkeypatch):
    monkeypatch.setattr(graph_module.extractor, "extract_claims", lambda text: [make_claim("c1")])
    monkeypatch.setattr(
        graph_module.prosecutor, "prosecute", lambda claim, opponent_argument=None: _arg(Stance.REFUTE, 0.2)
    )
    monkeypatch.setattr(
        graph_module.defender, "defend", lambda claim, opponent_argument=None: _arg(Stance.SUPPORT, 0.9)
    )
    monkeypatch.setattr(
        graph_module.judge, "judge", lambda claim, prosecution, defense: make_verdict(claim.id, 90)
    )

    graph_module._compiled_graph = None
    result = graph_module.run_audit("SpaceX launched 90 missions in 2023.")

    assert len(result.verdicts) == 1
    assert result.verdicts[0].confidence == 90
    assert result.arguments["c1"][0].stance == Stance.REFUTE
    assert result.arguments["c1"][1].stance == Stance.SUPPORT


def test_run_audit_triggers_rebuttal_loop_then_caps_at_two_rounds(monkeypatch):
    monkeypatch.setattr(graph_module.extractor, "extract_claims", lambda text: [make_claim("c1")])
    monkeypatch.setattr(
        graph_module.prosecutor, "prosecute", lambda claim, opponent_argument=None: _arg(Stance.REFUTE, 0.5)
    )
    monkeypatch.setattr(
        graph_module.defender, "defend", lambda claim, opponent_argument=None: _arg(Stance.SUPPORT, 0.5)
    )

    judge_calls = {"n": 0}

    def fake_judge(claim, prosecution, defense):
        judge_calls["n"] += 1
        return make_verdict(claim.id, 50, label="disputed")

    monkeypatch.setattr(graph_module.judge, "judge", fake_judge)

    graph_module._compiled_graph = None
    result = graph_module.run_audit("An ambiguous claim.")

    assert judge_calls["n"] == graph_module.config.MAX_REBUTTAL_ROUNDS
    assert len(result.verdicts) == 1
    assert result.verdicts[0].confidence == 50


def test_run_audit_survives_prosecutor_failure(monkeypatch):
    monkeypatch.setattr(graph_module.extractor, "extract_claims", lambda text: [make_claim("c1")])

    def broken_prosecute(claim, opponent_argument=None):
        raise RuntimeError("search API down")

    monkeypatch.setattr(graph_module.prosecutor, "prosecute", broken_prosecute)
    monkeypatch.setattr(
        graph_module.defender, "defend", lambda claim, opponent_argument=None: _arg(Stance.SUPPORT, 0.9)
    )
    monkeypatch.setattr(
        graph_module.judge, "judge", lambda claim, prosecution, defense: make_verdict(claim.id, 80)
    )

    graph_module._compiled_graph = None
    result = graph_module.run_audit("A resilience test claim.")

    assert len(result.verdicts) == 1
    assert result.verdicts[0].confidence == 80


def test_run_audit_multiple_claims_all_get_verdicts(monkeypatch):
    claims = [make_claim("c1"), make_claim("c2"), make_claim("c3")]
    monkeypatch.setattr(graph_module.extractor, "extract_claims", lambda text: claims)
    monkeypatch.setattr(
        graph_module.prosecutor, "prosecute", lambda claim, opponent_argument=None: _arg(Stance.REFUTE, 0.2)
    )
    monkeypatch.setattr(
        graph_module.defender, "defend", lambda claim, opponent_argument=None: _arg(Stance.SUPPORT, 0.9)
    )
    monkeypatch.setattr(
        graph_module.judge, "judge", lambda claim, prosecution, defense: make_verdict(claim.id, 85)
    )

    graph_module._compiled_graph = None
    result = graph_module.run_audit("Three claims in one text.")

    assert {v.claim_id for v in result.verdicts} == {"c1", "c2", "c3"}
