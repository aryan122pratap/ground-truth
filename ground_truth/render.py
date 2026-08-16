import html

from ground_truth.models import AuditResult, Verdict

LABEL_COLORS = {
    "supported": "#0d9488",
    "disputed": "#d97706",
    "contradicted": "#e11d48",
    "unverifiable": "#6b7280",
}
SKIPPED_COLOR = "#6b7280"


def _locate_claims(text: str, claims) -> list[tuple[int, int, object]]:
    located = []
    search_from = 0
    for claim in claims:
        idx = text.find(claim.original_sentence, search_from)
        if idx == -1:
            idx = text.find(claim.original_sentence)
        if idx == -1:
            continue
        located.append((idx, idx + len(claim.original_sentence), claim))
        search_from = idx + len(claim.original_sentence)
    located.sort(key=lambda t: t[0])
    return located


def _span_for_claim(text: str, start: int, end: int, claim, verdict: Verdict | None) -> str:
    if not claim.checkable:
        color = SKIPPED_COLOR
        badge = "–"
        title = f"{claim.claim_type} — not fact-checked"
    elif verdict is None:
        color = SKIPPED_COLOR
        badge = "–"
        title = "no verdict available"
    else:
        color = LABEL_COLORS.get(verdict.label, SKIPPED_COLOR)
        badge = str(verdict.confidence)
        title = f"{verdict.label} ({verdict.confidence}/100)"

    return (
        f'<span class="gt-claim" data-claim-id="{html.escape(claim.id)}" '
        f'title="{html.escape(title)}" '
        f'style="background-color:{color}33;border-bottom:2px solid {color};'
        f'padding:0 2px;border-radius:2px;">'
        f"{html.escape(text[start:end])}"
        f'<sup style="font-size:0.65em;color:{color};font-weight:700;margin-left:1px;">'
        f"{badge}</sup></span>"
    )


def render_annotated_html(result: AuditResult) -> str:
    """Render the original text with each audited sentence wrapped in a
    confidence-colored span. Sentences whose claim couldn't be located verbatim
    in the text (e.g. the model paraphrased slightly) are rendered as plain text
    rather than crashing — annotation is best-effort."""
    text = result.original_text
    verdict_by_claim = {v.claim_id: v for v in result.verdicts}
    located = _locate_claims(text, result.claims)

    parts: list[str] = []
    cursor = 0
    for start, end, claim in located:
        if start < cursor:
            continue
        parts.append(html.escape(text[cursor:start]))
        parts.append(_span_for_claim(text, start, end, claim, verdict_by_claim.get(claim.id)))
        cursor = end
    parts.append(html.escape(text[cursor:]))
    return "".join(parts)


def compute_summary(result: AuditResult) -> dict:
    """Evidence-weighted truthfulness score plus per-label counts, for the
    summary strip / bar chart."""
    verdicts = result.verdicts
    label_counts = {"supported": 0, "disputed": 0, "contradicted": 0, "unverifiable": 0}
    for v in verdicts:
        label_counts[v.label] = label_counts.get(v.label, 0) + 1

    if verdicts:
        weights = [max(len(v.key_citations), 1) for v in verdicts]
        overall_score = sum(v.confidence * w for v, w in zip(verdicts, weights)) / sum(weights)
    else:
        overall_score = None

    return {
        "overall_score": overall_score,
        "label_counts": label_counts,
        "claim_count": len(result.claims),
        "checkable_count": sum(1 for c in result.claims if c.checkable),
        "verdict_count": len(verdicts),
    }
