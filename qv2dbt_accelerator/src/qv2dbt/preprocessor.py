"""Stage 1: turn raw .qvs text into a clean list of statements.

Responsibilities:
  * strip QlikView comments  (// line, /* block */, and REM ...;)
  * collect SET / LET variable definitions and expand $(var) references
  * split the script into individual statements on top-level semicolons
    (semicolons inside quotes or INLINE [...] brackets are ignored)

The output is a list of ``(raw_statement, kind_hint)`` that the parser
classifies. Keeping tokenisation separate from parsing keeps both testable.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .models import QvVariable


_REM_COMMENT = re.compile(r"(?im)^\s*REM\b[^;]*;")
_SET_LET = re.compile(r"(?is)^\s*(SET|LET)\s+([A-Za-z_][\w]*)\s*=\s*(.*)$")
_VAR_REF = re.compile(r"\$\(([A-Za-z_][\w]*)\)")


@dataclass
class Statement:
    raw: str
    # cheap upfront hint of the statement type; the parser makes the final call.
    kind_hint: str


def strip_comments(text: str) -> str:
    """Remove //, /* */ and REM comments while preserving quoted strings.

    Critically, '//' inside a quoted literal (e.g. a 'lib://...' path) is NOT a
    comment, so the scan is quote-aware rather than a naive regex.
    """
    out: list[str] = []
    quote: str | None = None
    depth = 0  # inside [ ... ] (QlikView file paths/identifiers with '//')
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        nxt = text[i + 1] if i + 1 < n else ""
        if quote:
            out.append(ch)
            if ch == quote:
                quote = None
            i += 1
            continue
        if ch in ("'", '"'):
            quote = ch
            out.append(ch)
            i += 1
        elif ch == "[":
            depth += 1
            out.append(ch)
            i += 1
        elif ch == "]":
            depth = max(0, depth - 1)
            out.append(ch)
            i += 1
        elif depth > 0:
            out.append(ch)
            i += 1
        elif ch == "/" and nxt == "/":
            while i < n and text[i] != "\n":
                i += 1
        elif ch == "/" and nxt == "*":
            i += 2
            while i < n and not (text[i] == "*" and i + 1 < n and text[i + 1] == "/"):
                i += 1
            i += 2
            out.append(" ")
        else:
            out.append(ch)
            i += 1
    return _REM_COMMENT.sub(";", "".join(out))


def split_statements(text: str) -> list[str]:
    """Split on semicolons that are not inside quotes or [ ... ] brackets."""
    statements: list[str] = []
    buf: list[str] = []
    depth = 0            # INLINE [...] / field-name [...] bracket depth
    quote: str | None = None
    i = 0
    while i < len(text):
        ch = text[i]
        if quote:
            buf.append(ch)
            if ch == quote:
                quote = None
            i += 1
            continue
        if ch in ("'", '"'):
            quote = ch
            buf.append(ch)
        elif ch == "[":
            depth += 1
            buf.append(ch)
        elif ch == "]":
            depth = max(0, depth - 1)
            buf.append(ch)
        elif ch == ";" and depth == 0:
            stmt = "".join(buf).strip()
            if stmt:
                statements.append(stmt)
            buf = []
        else:
            buf.append(ch)
        i += 1
    tail = "".join(buf).strip()
    if tail:
        statements.append(tail)
    return statements


def _hint(stmt: str) -> str:
    s = stmt.lstrip().lower()
    if s.startswith(("set ", "let ")):
        return "variable"
    if "mapping load" in s.split(";")[0]:
        return "mapping"
    for kw in ("left join", "right join", "inner join", "outer join", "join"):
        if s.startswith(kw):
            return "join"
    if s.startswith(("left keep", "right keep", "inner keep", "keep")):
        return "keep"
    if s.startswith("concatenate"):
        return "concatenate"
    if s.startswith("drop "):
        return "drop"
    if s.startswith("rename "):
        return "rename"
    if s.startswith("store "):
        return "store"
    if s.startswith(("sub ", "call ", "for ", "next", "if ", "endif",
                     "loop", "do ", "switch", "end sub", "exit ")):
        return "control"
    if "load" in s:
        return "load"
    return "other"


def preprocess(text: str) -> tuple[list[Statement], list[QvVariable]]:
    """Full stage-1 pass. Returns (statements, variables)."""
    cleaned = strip_comments(text)
    raw_statements = split_statements(cleaned)

    variables: list[QvVariable] = []
    var_values: dict[str, str] = {}
    out: list[Statement] = []

    for raw in raw_statements:
        m = _SET_LET.match(raw)
        if m:
            kw, name, value = m.group(1), m.group(2), m.group(3).strip()
            # Strip a single surrounding pair of quotes from SET values.
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
                value = value[1:-1]
            variables.append(
                QvVariable(name=name, value=value, is_let=kw.upper() == "LET")
            )
            var_values[name] = value
            out.append(Statement(raw=raw, kind_hint="variable"))
            continue
        # Expand $(var) references using variables defined so far.
        expanded = _expand_vars(raw, var_values)
        out.append(Statement(raw=expanded, kind_hint=_hint(expanded)))

    return out, variables


def _expand_vars(text: str, values: dict[str, str]) -> str:
    def repl(match: re.Match) -> str:
        name = match.group(1)
        return values.get(name, match.group(0))

    # Expand up to 5 times to resolve nested variable references.
    for _ in range(5):
        new = _VAR_REF.sub(repl, text)
        if new == text:
            break
        text = new
    return text
