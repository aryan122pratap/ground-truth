from ground_truth import graph as graph_module
from ground_truth.models import Argument, Claim, Stance, Verdict


def make_claim(id_="c1") -> Claim:
    return Claim(id=id_, text="t", original_sentence="t", checkable=True, claim_type="factual")


def test_stream_audit_yields_status_then_result(monkeypatch):
    monkeypatch.setattr(
        graph_module.extractor, "extract_claims", lambda text: [make_claim("c1"), make_claim("c2")]
    )
    monkeypatch.setattr(
        graph_module.prosecutor, "prosecute", lambda claim, opponent_argument=None: Argument(
            stance=Stance.REFUTE, reasoning="r", evidence=[], strength=0.2
        )
    )
    monkeypatch.setattr(
        graph_module.defender, "defend", lambda claim, opponent_argument=None: Argument(
            stance=Stance.SUPPORT, reasoning="r", evidence=[], strength=0.9
        )
    )
    monkeypatch.setattr(
        graph_module.judge,
        "judge",
        lambda claim, prosecution, defense: Verdict(
            claim_id=claim.id, confidence=85, label="supported", reasoning="r", key_citations=[], dissent="d"
        ),
    )

    graph_module._compiled_graph = None
    events = list(graph_module.stream_audit("some text with two claims"))

    kinds = [k for k, _ in events]
    assert kinds[0] == "status"
    assert kinds[-1] == "result"
    assert kinds.count("status") >= 3  # extractor + 2x debate_claim (+ aggregate)

    status_messages = [payload for kind, payload in events if kind == "status"]
    assert any("Extracted" in m for m in status_messages)
    assert any("ruled supported" in m for m in status_messages)

    result = events[-1][1]
    assert len(result.verdicts) == 2
