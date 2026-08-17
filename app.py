import plotly.graph_objects as go
import streamlit as st

from ground_truth.graph import stream_audit
from ground_truth.render import LABEL_COLORS, SKIPPED_COLOR, compute_summary, render_annotated_html
from tests.fixtures.sample_texts import EXAMPLES

st.set_page_config(page_title="Ground Truth", page_icon="🔎", layout="wide")

LABEL_ICONS = {"supported": "🟢", "disputed": "🟡", "contradicted": "🔴", "unverifiable": "⚪"}
EXAMPLE_ICONS = {"Mostly true": "🏛️", "Mixed": "⚖️", "Mostly false": "🧪"}

_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}

body { background: #0a0710; }
[data-testid="stAppViewContainer"] { background: transparent; }
[data-testid="stHeader"] { background: transparent; }
[data-testid="stToolbar"] { background: transparent; }

/* Floating blurred blobs behind everything — the glassmorphism backdrop */
.gt-blob-layer { position: fixed; inset: 0; z-index: -1; overflow: hidden; pointer-events: none; }
.gt-blob { position: absolute; border-radius: 50%; filter: blur(90px); }
.gt-blob-1 { width: 480px; height: 480px; top: -140px; left: -120px; background: #8b5cf6; opacity: 0.5; animation: gt-float-a 24s ease-in-out infinite; }
.gt-blob-2 { width: 420px; height: 420px; top: 8%; right: -160px; background: #ec4899; opacity: 0.42; animation: gt-float-b 28s ease-in-out infinite; }
.gt-blob-3 { width: 400px; height: 400px; bottom: -140px; left: 22%; background: #f59e0b; opacity: 0.32; animation: gt-float-c 22s ease-in-out infinite; }
.gt-blob-4 { width: 340px; height: 340px; bottom: 6%; right: 8%; background: #f43f5e; opacity: 0.3; animation: gt-float-a 26s ease-in-out infinite reverse; }
@keyframes gt-float-a { 0%, 100% { transform: translate(0,0) scale(1); } 50% { transform: translate(50px,35px) scale(1.1); } }
@keyframes gt-float-b { 0%, 100% { transform: translate(0,0) scale(1); } 50% { transform: translate(-40px,45px) scale(0.92); } }
@keyframes gt-float-c { 0%, 100% { transform: translate(0,0) scale(1); } 50% { transform: translate(30px,-40px) scale(1.06); } }

@keyframes gt-fade-up { from { opacity: 0; transform: translateY(16px); } to { opacity: 1; transform: translateY(0); } }
.gt-anim-1 { animation: gt-fade-up 0.65s cubic-bezier(0.16,1,0.3,1) both; }
.gt-anim-2 { animation: gt-fade-up 0.65s cubic-bezier(0.16,1,0.3,1) 0.08s both; }
.gt-anim-3 { animation: gt-fade-up 0.65s cubic-bezier(0.16,1,0.3,1) 0.16s both; }

.block-container {
    max-width: 1120px;
    padding-top: 2.2rem;
    padding-bottom: 3rem;
}

/* Hero header */
.gt-eyebrow {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    font-size: 0.72rem;
    font-weight: 700;
    color: #e9d5ff;
    background: rgba(139,92,246,0.16);
    backdrop-filter: blur(10px);
    -webkit-backdrop-filter: blur(10px);
    border: 1px solid rgba(216,180,254,0.3);
    padding: 0.3rem 0.75rem;
    border-radius: 999px;
    margin-bottom: 1rem;
}
.gt-title {
    font-size: 3.4rem;
    font-weight: 900;
    letter-spacing: -0.03em;
    margin: 0 0 0.7rem 0;
    line-height: 1.05;
    background: linear-gradient(120deg, #ffffff 15%, #d8b4fe 50%, #f0abfc 75%, #fbcfe8 100%);
    -webkit-background-clip: text;
    background-clip: text;
    -webkit-text-fill-color: transparent;
    filter: drop-shadow(0 0 40px rgba(168,85,247,0.35));
}
.gt-sub {
    color: #cbc3d9;
    font-size: 1.08rem;
    line-height: 1.65;
    max-width: 680px;
    margin-bottom: 1.4rem;
}
.gt-sub a { color: #e9d5ff; text-decoration: none; font-weight: 600; }
.gt-sub a:hover { text-decoration: underline; }

.gt-badges { display: flex; gap: 0.6rem; flex-wrap: wrap; margin-bottom: 2.2rem; }
.gt-badge {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    font-size: 0.8rem;
    font-weight: 600;
    color: #e4defc;
    background: rgba(255,255,255,0.07);
    backdrop-filter: blur(10px);
    -webkit-backdrop-filter: blur(10px);
    border: 1px solid rgba(255,255,255,0.14);
    padding: 0.35rem 0.85rem;
    border-radius: 999px;
    transition: all 0.2s ease;
}
.gt-badge:hover { background: rgba(255,255,255,0.12); transform: translateY(-1px); }

/* How it works */
.gt-steps {
    display: flex;
    align-items: stretch;
    gap: 0.8rem;
    margin-bottom: 1.6rem;
}
.gt-step {
    flex: 1;
    background: rgba(255,255,255,0.055);
    backdrop-filter: blur(24px) saturate(150%);
    -webkit-backdrop-filter: blur(24px) saturate(150%);
    border: 1px solid rgba(255,255,255,0.14);
    border-radius: 18px;
    padding: 1.3rem 1.4rem;
    box-shadow: 0 8px 32px rgba(0,0,0,0.35), inset 0 1px 0 rgba(255,255,255,0.08);
    transition: all 0.25s cubic-bezier(0.16,1,0.3,1);
}
.gt-step:hover { transform: translateY(-4px); border-color: rgba(255,255,255,0.26); box-shadow: 0 14px 40px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.12); }
.gt-step-icon {
    width: 42px; height: 42px;
    display: flex; align-items: center; justify-content: center;
    border-radius: 12px;
    font-size: 1.25rem;
    margin-bottom: 0.7rem;
    background: linear-gradient(135deg, var(--c1), var(--c2));
    box-shadow: 0 4px 16px color-mix(in srgb, var(--c1) 50%, transparent);
}
.gt-step-title { font-weight: 700; font-size: 0.98rem; color: #f5f2fb; margin-bottom: 0.3rem; }
.gt-step-desc { font-size: 0.85rem; color: #b3a9c4; line-height: 1.5; }
.gt-arrow { display: flex; align-items: center; color: #6b5f80; font-size: 1.4rem; padding: 0 0.15rem; }
@media (max-width: 900px) { .gt-steps { flex-direction: column; } .gt-arrow { display: none; } }

/* Glass cards */
.gt-card, div[data-testid="stVerticalBlockBorderWrapper"]:has(textarea) {
    background: rgba(255,255,255,0.055) !important;
    backdrop-filter: blur(24px) saturate(150%);
    -webkit-backdrop-filter: blur(24px) saturate(150%);
    border: 1px solid rgba(255,255,255,0.14) !important;
    border-radius: 20px !important;
    padding: 1.5rem 1.7rem;
    margin-bottom: 1.3rem;
    box-shadow: 0 10px 36px rgba(0,0,0,0.35), inset 0 1px 0 rgba(255,255,255,0.08);
}
.gt-section-title {
    font-size: 1.08rem;
    font-weight: 700;
    margin-bottom: 0.3rem;
    color: #f5f2fb;
    display: flex;
    align-items: center;
    gap: 0.5rem;
}

/* Annotated text — slightly more opaque so claim-status colors stay crisp */
.gt-annotated {
    font-size: 1.08rem;
    line-height: 2.15;
    background: rgba(10,7,16,0.45);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 14px;
    padding: 1.2rem 1.4rem;
}
.gt-annotated .gt-claim {
    padding: 1px 3px;
    border-radius: 4px;
    transition: filter 0.15s ease;
}
.gt-annotated .gt-claim:hover { filter: brightness(1.4); cursor: help; }

/* Legend chips */
.gt-legend { display: flex; gap: 1.1rem; flex-wrap: wrap; margin-bottom: 1rem; }
.gt-legend-item { display: flex; align-items: center; gap: 0.4rem; font-size: 0.85rem; color: #b3a9c4; }
.gt-legend-dot {
    width: 10px; height: 10px; border-radius: 50%; display: inline-block;
    box-shadow: 0 0 8px 1px var(--dot-glow, transparent);
}

/* Stat tiles */
.gt-stats { display: grid; grid-template-columns: repeat(5, 1fr); gap: 0.9rem; }
.gt-stat {
    position: relative;
    overflow: hidden;
    background: rgba(255,255,255,0.05);
    backdrop-filter: blur(18px);
    -webkit-backdrop-filter: blur(18px);
    border: 1px solid rgba(255,255,255,0.12);
    border-radius: 14px;
    padding: 1rem 1.1rem;
    transition: transform 0.2s cubic-bezier(0.16,1,0.3,1), box-shadow 0.2s ease, border-color 0.2s ease;
}
.gt-stat:hover { transform: translateY(-4px) scale(1.02); box-shadow: 0 14px 30px color-mix(in srgb, var(--accent) 35%, transparent); border-color: color-mix(in srgb, var(--accent) 50%, transparent); }
.gt-stat::before {
    content: "";
    position: absolute; top: 0; left: 0; right: 0; height: 3px;
    background: var(--accent, #8b5cf6);
}
.gt-stat-value { font-size: 1.75rem; font-weight: 800; color: var(--accent, #f5f2fb); line-height: 1.1; }
.gt-stat-label { font-size: 0.78rem; color: #b3a9c4; margin-top: 0.3rem; font-weight: 500; }
@media (max-width: 900px) { .gt-stats { grid-template-columns: repeat(2, 1fr); } }

/* Buttons */
div[data-testid="stButton"] button[kind="secondary"] {
    border-radius: 999px;
    border: 1px solid rgba(255,255,255,0.14);
    background: rgba(255,255,255,0.06);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    color: #e4defc;
    transition: all 0.2s cubic-bezier(0.16,1,0.3,1);
}
div[data-testid="stButton"] button[kind="secondary"]:hover {
    border-color: rgba(216,180,254,0.5);
    background: rgba(139,92,246,0.18);
    color: #f0e6ff;
    transform: translateY(-2px);
}
div[data-testid="stButton"] button[kind="secondary"]:active { transform: translateY(0) scale(0.97); }

div[data-testid="stButton"] button[kind="primary"] {
    border-radius: 12px;
    font-weight: 700;
    background: linear-gradient(135deg, #7c3aed, #6366f1);
    border: none;
    box-shadow: 0 8px 26px rgba(124,58,237,0.45);
    transition: all 0.2s cubic-bezier(0.34,1.56,0.64,1);
}
div[data-testid="stButton"] button[kind="primary"] p,
div[data-testid="stButton"] button[kind="primary"] div {
    color: #ffffff !important;
}
div[data-testid="stButton"] button[kind="primary"]:disabled {
    background: rgba(255,255,255,0.06);
    box-shadow: none;
}
div[data-testid="stButton"] button[kind="primary"]:disabled p,
div[data-testid="stButton"] button[kind="primary"]:disabled div {
    color: #6b6480 !important;
}
div[data-testid="stButton"] button[kind="primary"]:not(:disabled):hover {
    transform: translateY(-2px) scale(1.015);
    box-shadow: 0 14px 34px rgba(124,58,237,0.6);
}
div[data-testid="stButton"] button[kind="primary"]:not(:disabled):active {
    transform: translateY(0) scale(0.98);
}

/* Input focus glow */
div[data-testid="stVerticalBlockBorderWrapper"]:has(textarea):focus-within {
    border-color: rgba(216,180,254,0.5) !important;
    box-shadow: 0 12px 36px rgba(0,0,0,0.4), 0 0 0 3px rgba(139,92,246,0.25) !important;
}
textarea { transition: all 0.2s ease; }

/* Expanders as glass claim cards */
div[data-testid="stExpander"] {
    border-radius: 14px !important;
    border: 1px solid rgba(255,255,255,0.12) !important;
    background: rgba(255,255,255,0.04) !important;
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
    margin-bottom: 0.6rem;
    box-shadow: 0 8px 22px rgba(0,0,0,0.28);
    transition: border-color 0.2s ease;
}
div[data-testid="stExpander"]:hover { border-color: rgba(216,180,254,0.35) !important; }

.gt-footer { color: #9089a3; font-size: 0.82rem; line-height: 1.6; }
</style>
"""
st.markdown(_CSS, unsafe_allow_html=True)

st.markdown(
    """
<div class="gt-blob-layer">
    <div class="gt-blob gt-blob-1"></div>
    <div class="gt-blob gt-blob-2"></div>
    <div class="gt-blob gt-blob-3"></div>
    <div class="gt-blob gt-blob-4"></div>
</div>
<div class="gt-anim-1">
<div class="gt-eyebrow">⚡ ADVERSARIAL FACT AUDITOR</div>
<div class="gt-title">Ground Truth</div>
<div class="gt-sub">Two AI agents argue for and against every claim in your text — a prosecutor
searching for refutation, a defender searching for confirmation — and a judge scores each one
with real citations and an honest dissenting view.
<a href="https://github.com/aryan122pratap/ground-truth" target="_blank">View on GitHub →</a></div>
<div class="gt-badges">
    <span class="gt-badge">🕸️ LangGraph</span>
    <span class="gt-badge">⚡ Groq</span>
    <span class="gt-badge">🔍 Live web search</span>
    <span class="gt-badge">🆓 Zero paid APIs</span>
</div>
</div>
<div class="gt-steps gt-anim-2">
    <div class="gt-step">
        <div class="gt-step-icon" style="--c1:#8b5cf6;--c2:#c4b5fd;">✂️</div>
        <div class="gt-step-title">1. Extract claims</div>
        <div class="gt-step-desc">Splits your text into atomic, checkable statements — skipping opinions and predictions.</div>
    </div>
    <div class="gt-arrow">→</div>
    <div class="gt-step">
        <div class="gt-step-icon" style="--c1:#ec4899;--c2:#f472b6;">⚔️</div>
        <div class="gt-step-title">2. Adversarial debate</div>
        <div class="gt-step-desc">A prosecutor and defender independently search the web and build opposing briefs.</div>
    </div>
    <div class="gt-arrow">→</div>
    <div class="gt-step">
        <div class="gt-step-icon" style="--c1:#f59e0b;--c2:#fbbf24;">⚖️</div>
        <div class="gt-step-title">3. Judge verdict</div>
        <div class="gt-step-desc">Weighs both briefs on evidence quality and always states the losing side's best point.</div>
    </div>
</div>
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
        icon = EXAMPLE_ICONS.get(label, "")
        col.button(f"{icon} {label}", width="stretch", on_click=_use_example, args=(sample_text,))
    run_clicked = st.button(
        "🚀 Run audit", type="primary", disabled=not st.session_state["input_text"].strip()
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
    st.markdown('<div class="gt-section-title">📝 Annotated text</div>', unsafe_allow_html=True)
    legend_items = [
        ("Supported", LABEL_COLORS["supported"]),
        ("Disputed", LABEL_COLORS["disputed"]),
        ("Contradicted", LABEL_COLORS["contradicted"]),
        ("Unverifiable / opinion", SKIPPED_COLOR),
    ]
    legend_html = "".join(
        f'<div class="gt-legend-item"><span class="gt-legend-dot" '
        f'style="background:{color};--dot-glow:{color}"></span>{name}</div>'
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
      <div class="gt-stat" style="--accent:#c4b5fd"><div class="gt-stat-value">{score_display}</div><div class="gt-stat-label">📊 Truthfulness score</div></div>
      <div class="gt-stat" style="--accent:{LABEL_COLORS['supported']}"><div class="gt-stat-value">{counts['supported']}</div><div class="gt-stat-label">🟢 Supported</div></div>
      <div class="gt-stat" style="--accent:{LABEL_COLORS['disputed']}"><div class="gt-stat-value">{counts['disputed']}</div><div class="gt-stat-label">🟡 Disputed</div></div>
      <div class="gt-stat" style="--accent:{LABEL_COLORS['contradicted']}"><div class="gt-stat-value">{counts['contradicted']}</div><div class="gt-stat-label">🔴 Contradicted</div></div>
      <div class="gt-stat" style="--accent:{SKIPPED_COLOR}"><div class="gt-stat-value">{counts['unverifiable']}</div><div class="gt-stat-label">⚪ Unverifiable</div></div>
    </div>
    """
    st.markdown('<div class="gt-card">', unsafe_allow_html=True)
    st.markdown('<div class="gt-section-title">📈 Summary</div>', unsafe_allow_html=True)
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
                textfont=dict(color="#f5f2fb"),
                customdata=[v.label for v in verdicts_sorted],
                hovertemplate="<b>%{y}</b><br>%{customdata} — %{x}/100<extra></extra>",
            )
        )
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(family="Inter, sans-serif", color="#b3a9c4", size=13),
            xaxis=dict(
                title="Confidence (0-100)",
                range=[0, 108],
                gridcolor="rgba(255,255,255,0.1)",
                zerolinecolor="rgba(255,255,255,0.1)",
            ),
            yaxis=dict(title=None, gridcolor="rgba(0,0,0,0)"),
            bargap=0.4,
            height=max(180, 55 + 42 * len(verdicts_sorted)),
            margin=dict(l=10, r=10, t=16, b=10),
        )
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown(
        '<div class="gt-section-title" style="margin-top:0.4rem;">🔍 Claim-by-claim verdicts</div>',
        unsafe_allow_html=True,
    )
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
<div class="gt-footer" style="margin-top:2rem; padding-top:1rem; border-top:1px solid rgba(255,255,255,0.1);">
⚠️ This is an AI-assisted research aid. Scores are model judgments over web search results,
not ground truth, and this tool is not a substitute for human fact-checking.
</div>
""",
    unsafe_allow_html=True,
)
