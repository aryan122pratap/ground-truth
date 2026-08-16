import operator
import time
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from ground_truth import config
from ground_truth.agents import defender, extractor, judge, prosecutor
from ground_truth.models import Argument, AuditResult, Claim, Stance, Verdict


def _merge_arguments(a: dict, b: dict) -> dict:
    merged = dict(a)
    merged.update(b)
    return merged


class AuditState(TypedDict):
    raw_text: str
    claims: list[Claim]
    arguments: Annotated[dict[str, list[Argument]], _merge_arguments]
    verdicts: Annotated[list[Verdict], operator.add]
    errors: Annotated[list[str], operator.add]


class ClaimState(TypedDict):
    claim: Claim
    round: int
    prosecution: Argument | None
    defense: Argument | None
    verdict: Verdict | None
    errors: Annotated[list[str], operator.add]


def _extractor_node(state: AuditState) -> dict:
    try:
        claims = extractor.extract_claims(state["raw_text"])
        return {"claims": claims}
    except Exception as exc:
        return {"claims": [], "errors": [f"claim extraction failed: {exc}"]}


def _route_after_extraction(state: AuditState):
    checkable = [c for c in state["claims"] if c.checkable]
    if not checkable:
        return END
    return [Send("debate_claim", {"claim": c}) for c in checkable]


def _prosecute_node(state: ClaimState) -> dict:
    try:
        arg = prosecutor.prosecute(state["claim"], opponent_argument=state.get("defense"))
        return {"prosecution": arg}
    except Exception as exc:
        fallback = Argument(
            stance=Stance.REFUTE,
            reasoning=f"Prosecutor agent failed: {exc}",
            evidence=[],
            strength=0.0,
        )
        return {"prosecution": fallback, "errors": [f"prosecutor failed for {state['claim'].id}: {exc}"]}


def _defend_node(state: ClaimState) -> dict:
    try:
        arg = defender.defend(state["claim"], opponent_argument=state.get("prosecution"))
        return {"defense": arg}
    except Exception as exc:
        fallback = Argument(
            stance=Stance.SUPPORT,
            reasoning=f"Defender agent failed: {exc}",
            evidence=[],
            strength=0.0,
        )
        return {"defense": fallback, "errors": [f"defender failed for {state['claim'].id}: {exc}"]}


def _judge_node(state: ClaimState) -> dict:
    claim = state["claim"]
    prosecution = state.get("prosecution") or Argument(
        stance=Stance.REFUTE, reasoning="Prosecutor produced no argument.", evidence=[], strength=0.0
    )
    defense = state.get("defense") or Argument(
        stance=Stance.SUPPORT, reasoning="Defender produced no argument.", evidence=[], strength=0.0
    )
    try:
        verdict = judge.judge(claim, prosecution, defense)
    except Exception as exc:
        verdict = Verdict(
            claim_id=claim.id,
            confidence=50,
            label="unverifiable",
            reasoning=f"Judge agent failed: {exc}",
            key_citations=[],
            dissent="The judge could not complete deliberation; treat this claim as unverified.",
        )
        return {"verdict": verdict, "round": state.get("round", 0) + 1, "errors": [f"judge failed for {claim.id}: {exc}"]}
    return {"verdict": verdict, "round": state.get("round", 0) + 1}


def _route_after_judge(state: ClaimState):
    verdict = state["verdict"]
    round_ = state.get("round", 0)
    ambiguous = config.AMBIGUOUS_CONFIDENCE_LOW <= verdict.confidence <= config.AMBIGUOUS_CONFIDENCE_HIGH
    if ambiguous and round_ < config.MAX_REBUTTAL_ROUNDS:
        return ["prosecute_node", "defend_node"]
    return END


def _build_claim_subgraph():
    graph = StateGraph(ClaimState)
    graph.add_node("prosecute_node", _prosecute_node)
    graph.add_node("defend_node", _defend_node)
    graph.add_node("judge_node", _judge_node)

    graph.add_edge(START, "prosecute_node")
    graph.add_edge(START, "defend_node")
    graph.add_edge("prosecute_node", "judge_node")
    graph.add_edge("defend_node", "judge_node")
    graph.add_conditional_edges(
        "judge_node",
        _route_after_judge,
        {"prosecute_node": "prosecute_node", "defend_node": "defend_node", END: END},
    )
    return graph.compile()


_claim_subgraph = _build_claim_subgraph()


def _debate_claim_node(state: dict) -> dict:
    claim: Claim = state["claim"]
    result = _claim_subgraph.invoke(
        {"claim": claim, "round": 0, "prosecution": None, "defense": None, "verdict": None, "errors": []}
    )
    update: dict = {"errors": result.get("errors", [])}
    if result.get("verdict") is not None:
        update["verdicts"] = [result["verdict"]]
    update["arguments"] = {claim.id: [result.get("prosecution"), result.get("defense")]}
    return update


def _aggregate_node(state: AuditState) -> dict:
    return {}


def build_graph():
    graph = StateGraph(AuditState)
    graph.add_node("extractor", _extractor_node)
    graph.add_node("debate_claim", _debate_claim_node)
    graph.add_node("aggregate", _aggregate_node)

    graph.add_edge(START, "extractor")
    graph.add_conditional_edges("extractor", _route_after_extraction, ["debate_claim", END])
    graph.add_edge("debate_claim", "aggregate")
    graph.add_edge("aggregate", END)
    return graph.compile()


_compiled_graph = None


def get_graph():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_graph()
    return _compiled_graph


def stream_audit(text: str):
    """Run the audit graph, yielding ('status', message) progress events as each
    node completes, followed by a final ('result', AuditResult) event."""
    start = time.monotonic()
    total_checkable = 0
    completed = 0
    final_state = None

    for mode, chunk in get_graph().stream(
        {"raw_text": text, "claims": [], "arguments": {}, "verdicts": [], "errors": []},
        stream_mode=["updates", "values"],
    ):
        if mode == "values":
            final_state = chunk
            continue
        for node_name, update in chunk.items():
            update = update or {}
            if node_name == "extractor":
                claims = update.get("claims", [])
                total_checkable = sum(1 for c in claims if c.checkable)
                if total_checkable:
                    yield (
                        "status",
                        f"Extracted {len(claims)} claim(s) — auditing {total_checkable} checkable...",
                    )
                else:
                    yield ("status", f"Extracted {len(claims)} claim(s) — none checkable, nothing to audit.")
            elif node_name == "debate_claim":
                completed += 1
                verdicts = update.get("verdicts", [])
                label = verdicts[0].label if verdicts else "unresolved"
                confidence = verdicts[0].confidence if verdicts else "?"
                total_display = total_checkable or completed
                yield (
                    "status",
                    f"Judge deliberating... claim {completed}/{total_display} ruled "
                    f"{label} ({confidence}/100).",
                )
            elif node_name == "aggregate":
                yield ("status", "Finalizing results...")

    elapsed = time.monotonic() - start
    final_state = final_state or {"claims": [], "arguments": {}, "verdicts": []}
    result = AuditResult(
        original_text=text,
        claims=final_state["claims"],
        arguments={k: [a for a in v if a is not None] for k, v in final_state["arguments"].items()},
        verdicts=final_state["verdicts"],
        elapsed_seconds=elapsed,
        model_used=config.select_model(),
    )
    yield ("result", result)


def run_audit(text: str) -> AuditResult:
    for kind, payload in stream_audit(text):
        if kind == "result":
            return payload
    raise RuntimeError("stream_audit did not yield a result")
