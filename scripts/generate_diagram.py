"""Generate assets/architecture.png from the compiled top-level LangGraph.

Usage: python scripts/generate_diagram.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ground_truth import graph as graph_module  # noqa: E402
from ground_truth.config import ROOT_DIR  # noqa: E402


def _render(graph_repr, name: str, assets_dir: Path) -> None:
    mermaid_source = graph_repr.draw_mermaid()
    (assets_dir / f"{name}.mmd").write_text(mermaid_source, encoding="utf-8")
    print(f"Wrote assets/{name}.mmd")

    try:
        png_bytes = graph_repr.draw_mermaid_png()
        (assets_dir / f"{name}.png").write_bytes(png_bytes)
        print(f"Wrote assets/{name}.png")
    except Exception as exc:
        print(f"Could not render {name}.png (needs network access to mermaid.ink): {exc}")
        print(f"assets/{name}.mmd was still written — README embeds the Mermaid source directly.")


def main() -> None:
    assets_dir = ROOT_DIR / "assets"
    assets_dir.mkdir(exist_ok=True)

    _render(graph_module.get_graph().get_graph(), "architecture", assets_dir)
    _render(graph_module._claim_subgraph.get_graph(), "claim_subgraph", assets_dir)


if __name__ == "__main__":
    main()
