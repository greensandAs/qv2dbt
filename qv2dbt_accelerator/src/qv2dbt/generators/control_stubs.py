"""Emit guided manual-conversion stubs for captured control-flow blocks."""
from __future__ import annotations

from ..models import QvScript


def generate(script: QvScript, path: str) -> int:
    blocks = script.control_blocks
    lines = [
        f"# Manual Conversion Stubs — {script.name}",
        "",
        "QlikView control flow has no row-level SQL equivalent, so these blocks "
        "were **not** auto-converted. Each is listed below with recommended "
        "conversion guidance. Inner `LOAD` statements were still parsed into "
        "models; only the control scaffolding needs manual work.",
        "",
    ]
    if not blocks:
        lines.append("_No control-flow constructs detected._\n")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines))
        return 0

    by_kind: dict[str, int] = {}
    for b in blocks:
        by_kind[b.kind] = by_kind.get(b.kind, 0) + 1
    lines.append("## Summary\n")
    lines.append("| Construct | Count |")
    lines.append("|---|---|")
    for k, n in sorted(by_kind.items()):
        lines.append(f"| `{k}` | {n} |")
    lines.append("")

    for i, b in enumerate(blocks, 1):
        lines.append(f"## {i}. `{b.kind}` (lines {b.start_line}–{b.end_line})\n")
        lines.append(f"**Guidance:** {b.guidance}\n")
        lines.append("```qlik")
        body = b.body if len(b.body) < 2000 else b.body[:2000] + "\n... (truncated)"
        lines.append(body)
        lines.append("```\n")

    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    return len(blocks)
