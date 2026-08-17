"""Smoke-test the audit graph end-to-end from the command line.

Usage: python scripts/run_cli.py "some text to audit"
"""

import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ground_truth.graph import run_audit  # noqa: E402


def main() -> None:
    if len(sys.argv) < 2:
        print('Usage: python scripts/run_cli.py "some text to audit"')
        raise SystemExit(1)

    text = sys.argv[1]
    result = run_audit(text)

    print(f"model: {result.model_used}")
    print(f"elapsed: {result.elapsed_seconds:.2f}s")
    print(f"claims extracted: {len(result.claims)}")
    for claim in result.claims:
        print(f"  [{claim.id}] ({claim.claim_type}, checkable={claim.checkable}) {claim.text}")

    print(f"verdicts: {len(result.verdicts)}")
    for verdict in result.verdicts:
        print(f"  [{verdict.claim_id}] {verdict.label} ({verdict.confidence}/100)")
        print(f"    reasoning: {verdict.reasoning}")
        print(f"    dissent: {verdict.dissent}")
        for citation in verdict.key_citations:
            print(f"    - {citation.url}")


if __name__ == "__main__":
    main()
