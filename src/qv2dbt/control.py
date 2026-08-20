"""Detect and structurally capture QlikView script control flow.

Control constructs (SUB/FOR/IF/DO/SWITCH and CALL/EXIT) have no row-level SQL
equivalent, so they are not translated. Instead they are captured as
:class:`QvControlBlock` objects with conversion guidance, surfaced in the
migration report and as manual-conversion stubs. Inner LOAD statements are
still parsed as tables (they carry real logic); only the control scaffolding is
recorded here.
"""
from __future__ import annotations

import re

from .models import QvControlBlock

# opener regex -> block kind
_OPENERS = [
    (re.compile(r"(?i)^sub\s+\w+"), "sub"),
    (re.compile(r"(?i)^for\s+each\b"), "for"),
    (re.compile(r"(?i)^for\b"), "for"),
    (re.compile(r"(?i)^do\b"), "do"),
    (re.compile(r"(?i)^switch\b"), "switch"),
    (re.compile(r"(?i)^if\b.*\bthen\s*;?\s*$"), "if"),  # block IF only
]
_CLOSERS = {
    "sub": re.compile(r"(?i)^end\s*sub\b"),
    "for": re.compile(r"(?i)^next\b"),
    "do": re.compile(r"(?i)^loop\b"),
    "switch": re.compile(r"(?i)^end\s*switch\b"),
    "if": re.compile(r"(?i)^end\s*if\b"),
}
_SINGLE = [
    (re.compile(r"(?i)^call\s+\w+"), "call"),
    (re.compile(r"(?i)^exit\s+script\b"), "exit"),
]

_GUIDANCE = {
    "sub": "SUB routine -> convert to a dbt macro (macros/) or a parameterised "
           "model; replace CALL sites with the macro/ref.",
    "for": "Loop (often over files/QVDs) -> in dbt use an external stage + one "
           "COPY/LOAD, or a for-loop over a var/seed that UNIONs sources.",
    "if": "Conditional script branch -> encode with dbt vars / target-based "
          "conditional refs; this is not a row-level WHERE.",
    "do": "Iterative DO..LOOP (often incremental) -> convert to an incremental "
          "dbt model or an orchestrated job.",
    "switch": "SWITCH branch -> select the model/logic via a dbt var conditional.",
    "call": "SUB invocation -> reference the converted macro/model.",
    "exit": "EXIT SCRIPT -> no equivalent; ensure downstream models still build.",
}


def find_control_blocks(cleaned_text: str) -> list[QvControlBlock]:
    lines = cleaned_text.splitlines()
    blocks: list[QvControlBlock] = []
    stack: list[tuple[str, int, str]] = []  # (kind, start_idx, header)

    for i, raw in enumerate(lines):
        line = raw.strip().rstrip(";").strip()
        if not line:
            continue

        # closer for the current open block?
        if stack:
            kind, start, header = stack[-1]
            if _CLOSERS[kind].match(line):
                stack.pop()
                if not stack:  # closed a top-level block
                    body = "\n".join(lines[start:i + 1])
                    blocks.append(QvControlBlock(
                        kind=kind, header=header.strip(), body=body,
                        start_line=start + 1, end_line=i + 1,
                        guidance=_GUIDANCE.get(kind, "")))
                continue

        # opener?
        opened = False
        for rx, kind in _OPENERS:
            if rx.match(line):
                stack.append((kind, i, line))
                opened = True
                break
        if opened:
            continue

        # single-line control (only at top level)
        if not stack:
            for rx, kind in _SINGLE:
                if rx.match(line):
                    blocks.append(QvControlBlock(
                        kind=kind, header=line, body=line,
                        start_line=i + 1, end_line=i + 1,
                        guidance=_GUIDANCE.get(kind, "")))
                    break

    # any unclosed opener -> record what we have (defensive)
    while stack:
        kind, start, header = stack.pop()
        if not stack:
            blocks.append(QvControlBlock(
                kind=kind, header=header.strip(),
                body="\n".join(lines[start:]),
                start_line=start + 1, end_line=len(lines),
                guidance=_GUIDANCE.get(kind, "") + " (block end not found)"))
    return blocks


def find_dynamic_variables(variables) -> list[str]:
    """Names of LET/SET variables whose value looks like generated code
    (contains LOAD/SQL/control keywords or nested $() expansion)."""
    flagged = []
    rx = re.compile(r"(?i)\b(load|select|resident|concatenate|if|for|sub)\b|\$\(")
    for v in variables:
        if v.value and rx.search(v.value):
            flagged.append(v.name)
    return flagged
