import plotly.graph_objects as go
import streamlit as st

from ground_truth.graph import stream_audit
from ground_truth.render import LABEL_COLORS, compute_summary, render_annotated_html
from tests.fixtures.sample_texts import EXAMPLES

st.set_page_config(page_title="Ground Truth", page_icon="🔎", layout="wide")

st.title("Ground Truth")
st.caption(
    "Adversarial multi-agent fact auditor — two AI agents argue for and against every "
    "claim, a judge scores it with citations. "
    "[GitHub](https://github.com/aryan122pratap/ground-truth)"
)

if "input_text" not in st.session_state:
    st.session_state["input_text"] = ""


def _use_example(text: str) -> None:
    st.session_state["input_text"] = text


st.text_area(
    "Paste text to audit",
    height=200,
    placeholder="Paste a news article, LinkedIn post, research abstract, or tweet thread...",
    key="input_text",
)

st.caption("Try an example:")
example_cols = st.columns(len(EXAMPLES))
for col, (label, sample_text) in zip(example_cols, EXAMPLES):
    col.button(label, use_container_width=True, on_click=_use_example, args=(sample_text,))

run_clicked = st.button(
    "Run audit", type="primary", disabled=not st.session_state["input_text"].strip()
)

if run_clicked:
    text = st.session_state["input_text"]
    result = None
    with st.status("Auditing claims...", expanded=True) as status:
        for kind, payload in stream_audit(text):
            if kind == "status":
                status.write(payload)
            elif kind == "result":
                result = payload
        status.update(label="Audit complete", state="complete", expanded=False)
    st.session_state["result"] = result
else:
    result = st.session_state.get("result")

if result is not None:
    st.divider()
    st.subheader("Annotated text")
    st.caption(
        "Hover a highlighted sentence for its verdict. "
        "Teal = supported, amber = disputed, rose = contradicted, grey = unverifiable/opinion."
    )
    st.markdown(render_annotated_html(result), unsafe_allow_html=True)

    st.divider()
    st.subheader("Summary")
    summary = compute_summary(result)
    score_col, supported_col, disputed_col, contradicted_col, unverifiable_col = st.columns(5)
    score = summary["overall_score"]
    score_col.metric("Truthfulness score", f"{score:.0f}/100" if score is not None else "—")
    supported_col.metric("Supported", summary["label_counts"]["supported"])
    disputed_col.metric("Disputed", summary["label_counts"]["disputed"])
    contradicted_col.metric("Contradicted", summary["label_counts"]["contradicted"])
    unverifiable_col.metric("Unverifiable", summary["label_counts"]["unverifiable"])

    if result.verdicts:
        verdicts_sorted = sorted(result.verdicts, key=lambda v: v.confidence)
        fig = go.Figure(
            go.Bar(
                x=[v.confidence for v in verdicts_sorted],
                y=[v.claim_id for v in verdicts_sorted],
                orientation="h",
                marker_color=[LABEL_COLORS.get(v.label, "#6b7280") for v in verdicts_sorted],
                text=[f"{v.confidence}" for v in verdicts_sorted],
                textposition="outside",
            )
        )
        fig.update_layout(
            xaxis_title="Confidence (0-100)",
            yaxis_title="Claim",
            xaxis_range=[0, 100],
            height=max(200, 60 + 40 * len(verdicts_sorted)),
            margin=dict(l=10, r=10, t=10, b=10),
        )
        st.plotly_chart(fig, use_container_width=True)

    st.divider()
    st.subheader("Claim-by-claim verdicts")
    verdict_by_claim = {v.claim_id: v for v in result.verdicts}
    for claim in result.claims:
        verdict = verdict_by_claim.get(claim.id)
        if verdict is None:
            continue
        with st.expander(f"[{verdict.confidence}/100] {verdict.label.upper()} — {claim.text}"):
            st.markdown(f"**Judge's reasoning:** {verdict.reasoning}")
            st.warning(f"**Dissent (strongest counter-point):** {verdict.dissent}")

            arguments = result.arguments.get(claim.id, [])
            prosecution = next((a for a in arguments if a is not None and a.stance.value == "refute"), None)
            defense = next((a for a in arguments if a is not None and a.stance.value == "support"), None)

            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**Prosecution (argues false)**")
                if prosecution:
                    st.write(prosecution.reasoning)
                    for e in prosecution.evidence:
                        st.markdown(f"- [{e.title}]({e.url}) ({e.source_domain})")
            with col2:
                st.markdown("**Defense (argues true)**")
                if defense:
                    st.write(defense.reasoning)
                    for e in defense.evidence:
                        st.markdown(f"- [{e.title}]({e.url}) ({e.source_domain})")

            if verdict.key_citations:
                st.markdown("**Key citations**")
                for c in verdict.key_citations:
                    st.markdown(f"- [{c.title}]({c.url}) ({c.source_domain}, credibility {c.credibility})")

st.divider()
st.caption(
    "This is an AI-assisted research aid. Scores are model judgments over web search "
    "results, not ground truth, and this tool is not a substitute for human fact-checking."
)
