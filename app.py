import streamlit as st

from ground_truth.graph import run_audit
from ground_truth.render import render_annotated_html

st.set_page_config(page_title="Ground Truth", page_icon="🔎", layout="wide")

st.title("Ground Truth")
st.caption(
    "Adversarial multi-agent fact auditor — two AI agents argue for and against every "
    "claim, a judge scores it with citations. "
    "[GitHub](https://github.com/aryan122pratap/ground-truth)"
)

text = st.text_area(
    "Paste text to audit",
    height=200,
    placeholder="Paste a news article, LinkedIn post, research abstract, or tweet thread...",
)

run_clicked = st.button("Run audit", type="primary", disabled=not text.strip())

if run_clicked:
    with st.spinner("Auditing claims — extracting, debating, and judging..."):
        result = st.session_state["result"] = run_audit(text)
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
