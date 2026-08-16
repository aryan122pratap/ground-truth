from ground_truth.models import AuditResult, Claim, Verdict
from ground_truth.render import compute_summary, render_annotated_html


def make_result() -> AuditResult:
    claims = [
        Claim(
            id="c1",
            text="SpaceX was founded by Elon Musk in 2002.",
            original_sentence="SpaceX was founded by Elon Musk in 2002.",
            checkable=True,
            claim_type="factual",
        ),
        Claim(
            id="c2",
            text="SpaceX is the most impressive company of our generation.",
            original_sentence="It's the most impressive company ever.",
            checkable=False,
            claim_type="opinion",
        ),
    ]
    verdicts = [
        Verdict(
            claim_id="c1",
            confidence=92,
            label="supported",
            reasoning="r",
            key_citations=[],
            dissent="one blog disputes the exact date",
        )
    ]
    text = "SpaceX was founded by Elon Musk in 2002. It's the most impressive company ever."
    return AuditResult(
        original_text=text,
        claims=claims,
        arguments={},
        verdicts=verdicts,
        elapsed_seconds=1.0,
        model_used="gemini/gemini-2.0-flash",
    )


def test_render_annotated_html_wraps_both_claims():
    html_out = render_annotated_html(make_result())
    assert 'data-claim-id="c1"' in html_out
    assert 'data-claim-id="c2"' in html_out
    assert "#0d9488" in html_out  # supported color
    assert "#6b7280" in html_out  # skipped/opinion color
    assert "92" in html_out  # confidence badge


def test_render_annotated_html_escapes_special_characters():
    claim = Claim(
        id="c1",
        text="x",
        original_sentence="<script>alert(1)</script>",
        checkable=False,
        claim_type="opinion",
    )
    result = AuditResult(
        original_text="<script>alert(1)</script>",
        claims=[claim],
        arguments={},
        verdicts=[],
        elapsed_seconds=1.0,
        model_used="m",
    )
    html_out = render_annotated_html(result)
    assert "<script>alert(1)</script>" not in html_out
    assert "&lt;script&gt;" in html_out


def test_render_annotated_html_handles_unmatched_sentence_gracefully():
    claim = Claim(
        id="c1",
        text="x",
        original_sentence="this sentence is not actually in the text",
        checkable=True,
        claim_type="factual",
    )
    result = AuditResult(
        original_text="Completely different original text.",
        claims=[claim],
        arguments={},
        verdicts=[],
        elapsed_seconds=1.0,
        model_used="m",
    )
    html_out = render_annotated_html(result)
    assert "Completely different original text." in html_out
    assert "data-claim-id" not in html_out


def test_compute_summary_counts_and_score():
    summary = compute_summary(make_result())
    assert summary["claim_count"] == 2
    assert summary["checkable_count"] == 1
    assert summary["verdict_count"] == 1
    assert summary["label_counts"]["supported"] == 1
    assert summary["overall_score"] == 92


def test_compute_summary_no_verdicts():
    result = AuditResult(
        original_text="x",
        claims=[],
        arguments={},
        verdicts=[],
        elapsed_seconds=1.0,
        model_used="m",
    )
    summary = compute_summary(result)
    assert summary["overall_score"] is None
