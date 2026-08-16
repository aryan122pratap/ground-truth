import plotly.graph_objects as go
import streamlit as st

from ground_truth.graph import stream_audit
from ground_truth.render import LABEL_COLORS, SKIPPED_COLOR, compute_summary, render_annotated_html
from tests.fixtures.sample_texts import EXAMPLES

st.set_page_config(page_title="Ground Truth", page_icon="🔎", layout="wide")

LABEL_ICONS = {"supported": "🟢", "disputed": "🟡", "contradicted": "🔴", "unverifiable": "⚪"}

_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}

.block-container {
    max-width: 1100px;
    padding-top: 2.5rem;
    padding-bottom: 3rem;
}

/* Hero header */
.gt-eyebrow {
    text-transform: uppercase;
    letter-spacing: 0.14em;
    font-size: 0.72rem;
    font-weight: 600;
    color: #0d9488;
    margin-bottom: 0.4rem;
}
.gt-title {
    font-size: 2.6rem;
    font-weight: 800;
    letter-spacing: -0.02em;
    margin: 0 0 0.5rem 0;
    background: linear-gradient(135deg, #e6edf3 30%, #5eead4 100%);
    -webkit-background-clip: text;
    background-clip: text;
    -webkit-text-fill-color: transparent;
}
.gt-sub {
    color: #9aa7b5;
    font-size: 1.02rem;
    line-height: 1.6;
    max-width: 640px;
    margin-bottom: 1.6rem;
}
.gt-sub a { color: #5eead4; text-decoration: none; }
.gt-sub a:hover { text-decoration: underline; }

/* Cards */
.gt-card {
    background: #151b23;
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 14px;
    padding: 1.4rem 1.6rem;
    margin-bottom: 1.2rem;
}
.gt-section-title {
    font-size: 1.05rem;
    font-weight: 700;
    margin-bottom: 0.2rem;
    color: #e6edf3;
}
.gt-section-caption {
    color: #8b98a6;
    font-size: 0.88rem;
    margin-bottom: 1rem;
}

/* Annotated text */
.gt-annotated {
    font-size: 1.05rem;
    line-height: 2.1;
}
.gt-annotated .gt-claim {
    padding: 1px 3px;
    border-radius: 4px;
    transition: filter 0.15s ease;
}
.gt-annotated .gt-claim:hover { filter: brightness(1.35); cursor: help; }

/* Legend chips */
.gt-legend { display: flex; gap: 1.1rem; flex-wrap: wrap; margin-bottom: 1rem; }
.gt-legend-item { display: flex; align-items: center; gap: 0.4rem; font-size: 0.85rem; color: #9aa7b5; }
.gt-legend-dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; }

/* Stat tiles */
.gt-stats { display: grid; grid-template-columns: repeat(5, 1fr); gap: 0.8rem; }
.gt-stat {
    background: #10151b;
    border: 1px solid rgba(255,255,255,0.07);
    border-top: 3px solid var(--accent, #0d9488);
    border-radius: 10px;
    padding: 0.9rem 1rem;
}
.gt-stat-value { font-size: 1.6rem; font-weight: 800; color: var(--accent, #e6edf3); line-height: 1.1; }
.gt-stat-label { font-size: 0.78rem; color: #8b98a6; margin-top: 0.25rem; }
@media (max-width: 900px) { .gt-stats { grid-template-columns: repeat(2, 1fr); } }

/* Buttons */
div[data-testid="stButton"] button[kind="secondary"] {
    border-radius: 999px;
    border: 1px solid rgba(255,255,255,0.12);
    background: #151b23;
}
div[data-testid="stButton"] button[kind="secondary"]:hover {
    border-color: #0d9488;
    color: #5eead4;
}
div[data-testid="stButton"] button[kind="primary"] {
    border-radius: 8px;
    font-weight: 700;
}

/* Expanders as claim cards */
div[data-testid="stExpander"] {
    border-radius: 10px !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
    margin-bottom: 0.5rem;
}

.gt-footer { color: #6b7280; font-size: 0.82rem; line-height: 1.6; }
</style>
"""
st.markdown(_CSS, unsafe_allow_html=True)

st.markdown(
    """
<div class="gt-eyebrow">ADVERSARIAL FACT AUDITOR</div>
<div class="gt-title">Ground Truth</div>
<div class="gt-sub">Two AI agents argue for and against every claim in your text — a prosecutor
searching for refutation, a defender searching for confirmation — and a judge scores each one
with real citations and an honest dissenting view.
<a href="https://github.com/aryan122pratap/ground-truth" target="_blank">View on GitHub →</a></div>
""",
    unsafe_allow_html=True,
)

if "input_text" not in st.session_state:
    st.session_state["input_text"] = ""


def _use_example(text: str) -> None:
    st.session_state["input_text"] = text


with st.container(border=True):
    st.text_area(
        "Paste text to audit",
        height=180,
        placeholder="Paste a news article, LinkedIn post, research abstract, or tweet thread...",
        key="input_text",
        label_visibility="collapsed",
    )
    st.caption("Try an example:")
    example_cols = st.columns(len(EXAMPLES) + 2)
    for col, (label, sample_text) in zip(example_cols, EXAMPLES):
        col.button(label, width="stretch", on_click=_use_example, args=(sample_text,))
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
    st.markdown('<div class="gt-card">', unsafe_allow_html=True)
    st.markdown('<div class="gt-section-title">Annotated text</div>', unsafe_allow_html=True)
    legend_items = [
        ("Supported", LABEL_COLORS["supported"]),
        ("Disputed", LABEL_COLORS["disputed"]),
        ("Contradicted", LABEL_COLORS["contradicted"]),
        ("Unverifiable / opinion", SKIPPED_COLOR),
    ]
    legend_html = "".join(
        f'<div class="gt-legend-item"><span class="gt-legend-dot" '
        f'style="background:{color}"></span>{name}</div>'
        for name, color in legend_items
    )
    st.markdown(f'<div class="gt-legend">{legend_html}</div>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="gt-annotated">{render_annotated_html(result)}</div>', unsafe_allow_html=True
    )
    st.markdown("</div>", unsafe_allow_html=True)

    summary = compute_summary(result)
    score = summary["overall_score"]
    score_display = f"{score:.0f}" if score is not None else "—"
    counts = summary["label_counts"]
    stats_html = f"""
    <div class="gt-stats">
      <div class="gt-stat" style="--accent:#5eead4"><div class="gt-stat-value">{score_display}</div><div class="gt-stat-label">Truthfulness score</div></div>
      <div class="gt-stat" style="--accent:{LABEL_COLORS['supported']}"><div class="gt-stat-value">{counts['supported']}</div><div class="gt-stat-label">Supported</div></div>
      <div class="gt-stat" style="--accent:{LABEL_COLORS['disputed']}"><div class="gt-stat-value">{counts['disputed']}</div><div class="gt-stat-label">Disputed</div></div>
      <div class="gt-stat" style="--accent:{LABEL_COLORS['contradicted']}"><div class="gt-stat-value">{counts['contradicted']}</div><div class="gt-stat-label">Contradicted</div></div>
      <div class="gt-stat" style="--accent:{SKIPPED_COLOR}"><div class="gt-stat-value">{counts['unverifiable']}</div><div class="gt-stat-label">Unverifiable</div></div>
    </div>
    """
    st.markdown('<div class="gt-card">', unsafe_allow_html=True)
    st.markdown('<div class="gt-section-title">Summary</div>', unsafe_allow_html=True)
    st.markdown(stats_html, unsafe_allow_html=True)

    if result.verdicts:
        verdicts_sorted = sorted(result.verdicts, key=lambda v: v.confidence)
        fig = go.Figure(
            go.Bar(
                x=[v.confidence for v in verdicts_sorted],
                y=[v.claim_id for v in verdicts_sorted],
                orientation="h",
                marker=dict(
                    color=[LABEL_COLORS.get(v.label, SKIPPED_COLOR) for v in verdicts_sorted],
                    line_width=0,
                ),
                text=[f"{v.confidence}" for v in verdicts_sorted],
                textposition="outside",
                textfont=dict(color="#e6edf3"),
                customdata=[v.label for v in verdicts_sorted],
                hovertemplate="<b>%{y}</b><br>%{customdata} — %{x}/100<extra></extra>",
            )
        )
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(family="Inter, sans-serif", color="#9aa7b5", size=13),
            xaxis=dict(
                title="Confidence (0-100)",
                range=[0, 108],
                gridcolor="rgba(255,255,255,0.08)",
                zerolinecolor="rgba(255,255,255,0.08)",
            ),
            yaxis=dict(title=None, gridcolor="rgba(0,0,0,0)"),
            bargap=0.4,
            height=max(180, 55 + 42 * len(verdicts_sorted)),
            margin=dict(l=10, r=10, t=16, b=10),
        )
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="gt-section-title" style="margin-top:0.4rem;">Claim-by-claim verdicts</div>', unsafe_allow_html=True)
    verdict_by_claim = {v.claim_id: v for v in result.verdicts}
    for claim in result.claims:
        verdict = verdict_by_claim.get(claim.id)
        if verdict is None:
            continue
        icon = LABEL_ICONS.get(verdict.label, "⚪")
        with st.expander(f"{icon} [{verdict.confidence}/100] {verdict.label.upper()} — {claim.text}"):
            st.markdown(f"**Judge's reasoning:** {verdict.reasoning}")
            st.warning(f"**Dissent (strongest counter-point):** {verdict.dissent}")

            arguments = result.arguments.get(claim.id, [])
            prosecution = next((a for a in arguments if a is not None and a.stance.value == "refute"), None)
            defense = next((a for a in arguments if a is not None and a.stance.value == "support"), None)

            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**⚔️ Prosecution** *(argues false)*")
                if prosecution:
                    st.write(prosecution.reasoning)
                    for e in prosecution.evidence:
                        st.markdown(f"- [{e.title}]({e.url}) ({e.source_domain})")
            with col2:
                st.markdown("**🛡️ Defense** *(argues true)*")
                if defense:
                    st.write(defense.reasoning)
                    for e in defense.evidence:
                        st.markdown(f"- [{e.title}]({e.url}) ({e.source_domain})")

            if verdict.key_citations:
                st.markdown("**Key citations**")
                for c in verdict.key_citations:
                    st.markdown(f"- [{c.title}]({c.url}) ({c.source_domain}, credibility {c.credibility})")

st.markdown(
    """
<div class="gt-footer" style="margin-top:2rem; padding-top:1rem; border-top:1px solid rgba(255,255,255,0.08);">
This is an AI-assisted research aid. Scores are model judgments over web search results,
not ground truth, and this tool is not a substitute for human fact-checking.
</div>
""",
    unsafe_allow_html=True,
)
