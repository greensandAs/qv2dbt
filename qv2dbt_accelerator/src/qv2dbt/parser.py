"""Stage 2: classify statements and build the QvScript IR.

The parser is deliberately tolerant: QlikView load scripts are not a strict
grammar, so anything it cannot confidently interpret is preserved verbatim and
recorded (either as a field/table warning, or in ``QvScript.unsupported``) so
nothing is silently lost. That audit trail is what the migration report is
built from.
"""
from __future__ import annotations

import os
import re

from .models import (
    JoinKind,
    LoadKind,
    QvField,
    QvJoin,
    QvMap,
    QvScript,
    QvSource,
    QvTable,
)
from .preprocessor import Statement, preprocess


# --- small tokenizer helpers -------------------------------------------------

def split_top_level(text: str, sep: str = ",") -> list[str]:
    """Split on `sep` that is not nested in (), [] or quotes."""
    parts: list[str] = []
    buf: list[str] = []
    depth = 0
    quote: str | None = None
    for ch in text:
        if quote:
            buf.append(ch)
            if ch == quote:
                quote = None
            continue
        if ch in ("'", '"'):
            quote = ch
            buf.append(ch)
        elif ch in "([":
            depth += 1
            buf.append(ch)
        elif ch in ")]":
            depth -= 1
            buf.append(ch)
        elif ch == sep and depth == 0:
            parts.append("".join(buf).strip())
            buf = []
        else:
            buf.append(ch)
    if "".join(buf).strip():
        parts.append("".join(buf).strip())
    return parts


def _find_kw(text: str, keyword: str) -> int:
    """Case-insensitive position of a whole-word keyword at top level."""
    pat = re.compile(rf"\b{re.escape(keyword)}\b", re.IGNORECASE)
    depth = 0
    quote: str | None = None
    for m in pat.finditer(text):
        seg = text[: m.start()]
        depth = seg.count("(") - seg.count(")") + seg.count("[") - seg.count("]")
        # crude but effective: only accept when not inside brackets/quotes
        if depth == 0 and seg.count("'") % 2 == 0 and seg.count('"') % 2 == 0:
            return m.start()
    return -1


def _clean_ident(name: str) -> str:
    return name.strip().strip("[]").strip('"').strip("'").strip()


# --- field list parsing ------------------------------------------------------

_AS = re.compile(r"(?is)^(.*?)\s+as\s+([\[\"].*?[\]\"]|[A-Za-z_][\w$]*)\s*$")


def parse_fields(field_text: str) -> list[QvField]:
    fields: list[QvField] = []
    for chunk in split_top_level(field_text):
        if not chunk:
            continue
        m = _AS.match(chunk)
        if m:
            expr = m.group(1).strip()
            alias = _clean_ident(m.group(2))
            passthrough = bool(re.fullmatch(r"[\[\]\"\w$. ]+", expr))
            fields.append(
                QvField(source_expr=expr, alias=alias, is_passthrough=passthrough)
            )
        else:
            alias = _clean_ident(chunk)
            fields.append(
                QvField(source_expr=chunk.strip(), alias=alias, is_passthrough=True)
            )
    return fields


# --- source clause parsing ---------------------------------------------------

def _source_of_locator(locator: str) -> LoadKind:
    low = locator.lower()
    if low.endswith(".qvd") or "(qvd)" in low:
        return LoadKind.QVD
    if low.endswith((".csv", ".txt", ".xlsx", ".xls")):
        return LoadKind.FILE
    return LoadKind.FILE


def _source_identifier(locator: str) -> str:
    base = os.path.basename(locator.strip().strip("[]").strip("'\""))
    base = re.sub(r"\.(qvd|csv|txt|xlsx|xls)$", "", base, flags=re.IGNORECASE)
    base = re.sub(r"[^\w]+", "_", base).strip("_").lower()
    return base or "unknown_source"


class Parser:
    def __init__(self, script_name: str):
        self.script = QvScript(name=script_name)
        self._order = 0

    # -- public ---------------------------------------------------------------

    def parse(self, statements: list[Statement]) -> QvScript:
        i = 0
        while i < len(statements):
            stmt = statements[i]
            hint = stmt.kind_hint
            if hint in ("join", "keep", "concatenate"):
                self._parse_join(stmt)
            elif hint == "mapping":
                self._parse_mapping(stmt)
            elif hint == "load":
                self._parse_load(stmt)
            elif hint in ("drop", "rename", "store", "control"):
                self._record_unsupported(stmt)
            # 'variable' and 'other' need no table work here.
            i += 1
        self._assign_layers()
        self._collect_sources()
        self._detect_duplicate_names()
        return self.script

    def _detect_duplicate_names(self):
        """QlikView auto-concatenates same-named LOADs into one table. The
        accelerator emits a model per LOAD, so duplicates are flagged for the
        engineer to merge (usually via UNION ALL)."""
        seen: dict[str, int] = {}
        for t in self.script.tables:
            seen[t.name.lower()] = seen.get(t.name.lower(), 0) + 1
        for t in self.script.tables:
            if seen[t.name.lower()] > 1:
                t.warnings.append(
                    f"Table '{t.name}' is defined by multiple LOADs - QlikView "
                    f"auto-concatenates these; review/merge the generated "
                    f"models (likely UNION ALL).")
        for name, count in seen.items():
            if count > 1:
                self.script.unsupported.append(
                    {"kind": "implicit_concatenation",
                     "reason": f"Table '{name}' loaded {count}x "
                               f"(QlikView auto-concatenation)",
                     "raw": ""})

    # -- LOAD -----------------------------------------------------------------

    def _split_load(self, body: str):
        """Return (distinct, field_text, source_clause, where, group_by)."""
        distinct = False
        # A LOAD may carry prefixes before the LOAD keyword
        # (noconcatenate, concatenate, add, replace, buffer, first N).
        # Skip everything up to and including the LOAD keyword.
        m = re.search(r"(?is)\bload\b", body)
        rest = body[m.end():] if m else body
        if re.match(r"(?is)^distinct\s+", rest):
            distinct = True
            rest = re.sub(r"(?is)^distinct\s+", "", rest)

        # locate the earliest source/clause keyword at top level
        markers = ["resident", "from", "inline", "autogenerate"]
        cut = len(rest)
        which = None
        for kw in markers:
            pos = _find_kw(rest, kw)
            if 0 <= pos < cut:
                cut = pos
                which = kw
        field_text = rest[:cut].strip()
        source_part = rest[cut:].strip()
        # Strip the leading source keyword (FROM/RESIDENT/INLINE/AUTOGENERATE)
        # so only the locator/table name remains.
        if which:
            source_part = re.sub(rf"(?is)^{which}\s+", "", source_part, count=1)

        where_raw = group_by = None
        source_clause = source_part
        wpos = _find_kw(source_part, "where")
        gpos = _find_kw(source_part, "group by")
        end = len(source_part)
        if gpos != -1:
            group_by = source_part[gpos + len("group by"):].strip()
            end = min(end, gpos)
        if wpos != -1:
            where_raw = source_part[wpos + len("where"):].strip()
            # trim a trailing GROUP BY that followed WHERE
            if group_by and gpos > wpos:
                where_raw = source_part[wpos + len("where"):gpos].strip()
            end = min(end, wpos)
        source_clause = source_part[:end].strip()
        return distinct, field_text, which, source_clause, where_raw, group_by

    def _table_name_and_body(self, raw: str) -> tuple[str | None, str]:
        # Match table name labels: single word, [bracketed], or multi-word with spaces
        # Optionally followed by a (annotation) before the colon
        m = re.match(
            r"(?is)^\s*([A-Za-z_][\w$]*(?:\s+[\w$]+)*|\[[^\]]+\])"
            r"\s*(?:\([^)]*\))?\s*:\s*(.*)$", raw)
        if m and re.search(r"(?is)\b(load|sql)\b", m.group(2).lstrip()[:60]):
            return _clean_ident(m.group(1)), m.group(2).strip()
        return None, raw.strip()

    def _parse_load(self, stmt: Statement, forced_name: str | None = None):
        name, body = self._table_name_and_body(stmt.raw)
        name = forced_name or name or f"table_{self._order + 1}"

        # Detect SQL pass-through: body starts with SQL\s+SELECT (no LOAD keyword)
        sql_match = re.match(r"(?is)^(?:\([^)]*\)\s*)?SQL\s+(select\b.*)$", body)
        if sql_match:
            self._order += 1
            table = QvTable(
                name=name,
                kind=LoadKind.SQL,
                fields=[],
                source=sql_match.group(1).strip(),
                order=self._order,
                raw=stmt.raw,
            )
            self.script.tables.append(table)
            return
        distinct, field_text, which, source_clause, where_raw, group_by = \
            self._split_load(body)

        kind = LoadKind.RESIDENT
        source = None
        if which == "from":
            kind = _source_of_locator(source_clause)
            source = _clean_ident(re.split(r"\(", source_clause)[0])
        elif which == "resident":
            kind = LoadKind.RESIDENT
            source = _clean_ident(source_clause)
        elif which == "inline":
            kind = LoadKind.INLINE
            source = source_clause
        elif which == "autogenerate":
            kind = LoadKind.AUTOGEN
            source = source_clause
        else:
            # No source keyword: SQL SELECT pass-through or a preceding LOAD.
            if re.search(r"(?is)\bselect\b", field_text):
                kind = LoadKind.SQL
                source = field_text
                field_text = ""

        self._order += 1
        table = QvTable(
            name=name,
            kind=kind,
            fields=parse_fields(field_text) if field_text else [],
            source=source,
            where_raw=where_raw,
            group_by=split_top_level(group_by) if group_by else [],
            distinct=distinct,
            order=self._order,
            raw=stmt.raw,
        )
        if group_by:
            table.warnings.append(
                "Aggregating LOAD (GROUP BY) - verify aggregate expressions."
            )
        if kind == LoadKind.AUTOGEN:
            table.warnings.append("AUTOGENERATE has no relational equivalent.")
        self.script.tables.append(table)

    # -- JOIN / KEEP / CONCATENATE -------------------------------------------

    def _parse_join(self, stmt: Statement):
        raw = stmt.raw
        low = raw.lower()
        if low.startswith("left"):
            kind = JoinKind.LEFT
        elif low.startswith("right"):
            kind = JoinKind.RIGHT
        elif low.startswith("inner"):
            kind = JoinKind.INNER
        elif low.startswith("outer"):
            kind = JoinKind.OUTER
        elif low.startswith("concatenate"):
            kind = JoinKind.CONCATENATE
        else:
            kind = JoinKind.INNER

        # Optional (TargetTable) after the join keyword.
        target = None
        mt = re.search(r"(?is)^\s*(?:left|right|inner|outer|)\s*"
                       r"(?:join|keep|concatenate)\s*\(([^)]+)\)", raw)
        if mt:
            target = _clean_ident(mt.group(1))

        # The LOAD that supplies the joined rows.
        lpos = _find_kw(raw, "load")
        if lpos == -1:
            self._record_unsupported(stmt, reason="join without LOAD")
            return
        load_body = raw[lpos:]
        # Parse the joined LOAD as its own (intermediate) table.
        synthetic = f"{(target or self._prev_table_name())}__join{self._order + 1}"
        self._parse_load(Statement(raw=load_body, kind_hint="load"),
                         forced_name=synthetic)
        joined_tbl = self.script.tables[-1]

        base = self.script.table_by_name(target) if target else \
            self._prev_table(exclude=joined_tbl)
        if base is None:
            joined_tbl.warnings.append("Join target table not found in script.")
            return
        base.joins.append(
            QvJoin(kind=kind, right_table=joined_tbl.name, implicit_keys=True)
        )
        joined_tbl.layer = "intermediate"

    def _prev_table(self, exclude: QvTable | None = None) -> QvTable | None:
        for t in reversed(self.script.tables):
            if t is not exclude:
                return t
        return None

    def _prev_table_name(self) -> str:
        t = self._prev_table()
        return t.name if t else "base"

    # -- MAPPING LOAD ---------------------------------------------------------

    def _parse_mapping(self, stmt: Statement):
        name, body = self._table_name_and_body(stmt.raw)
        _, field_text, which, source_clause, _, _ = self._split_load(
            re.sub(r"(?is)\bmapping\s+load\b", "LOAD", body, count=1)
        )
        fields = parse_fields(field_text)
        key = fields[0].source_expr if fields else ""
        val = fields[1].source_expr if len(fields) > 1 else ""
        source = None
        if which == "resident":
            source = _clean_ident(source_clause)
        elif which == "from":
            source = _clean_ident(re.split(r"\(", source_clause)[0])
        self.script.maps.append(
            QvMap(name=name or f"map_{len(self.script.maps)+1}",
                  source=source, key_expr=key, value_expr=val, raw=stmt.raw)
        )

    # -- unsupported ----------------------------------------------------------

    def _record_unsupported(self, stmt: Statement, reason: str | None = None):
        kind = stmt.kind_hint
        if kind == "drop":
            m = re.search(r"(?is)drop\s+table[s]?\s+(.+)", stmt.raw)
            if m:
                for t in split_top_level(m.group(1)):
                    self.script.dropped_tables.append(_clean_ident(t))
        self.script.unsupported.append(
            {"kind": kind, "reason": reason or f"{kind} statement",
             "raw": stmt.raw.strip()[:400]}
        )

    # -- post processing ------------------------------------------------------

    def _assign_layers(self):
        source_kinds = {LoadKind.QVD, LoadKind.FILE, LoadKind.SQL, LoadKind.INLINE}
        for t in self.script.tables:
            if t.layer == "intermediate" and t.kind in source_kinds and not t.joins:
                t.layer = "staging"

    def _collect_sources(self):
        seen: dict[str, QvSource] = {}
        for t in self.script.tables:
            if t.kind in (LoadKind.QVD, LoadKind.FILE, LoadKind.SQL) and t.source:
                ident = _source_identifier(t.source) if t.kind != LoadKind.SQL \
                    else t.name.lower()
                if ident not in seen:
                    seen[ident] = QvSource(
                        identifier=ident, kind=t.kind, locator=t.source,
                        fields=[f.alias for f in t.fields],
                    )
        self.script.sources = list(seen.values())


def parse_script(text: str, script_name: str) -> QvScript:
    from .control import find_control_blocks, find_dynamic_variables
    from .preprocessor import strip_comments

    statements, variables = preprocess(text)
    parser = Parser(script_name)
    script = parser.parse(statements)
    script.variables = variables

    # Structurally capture control flow (SUB/FOR/IF/DO/SWITCH/CALL).
    script.control_blocks = find_control_blocks(strip_comments(text))
    for cb in script.control_blocks:
        script.unsupported.append({
            "kind": f"control:{cb.kind}",
            "reason": cb.guidance,
            "raw": cb.header[:120],
        })
    for vname in find_dynamic_variables(variables):
        script.unsupported.append({
            "kind": "dynamic_variable",
            "reason": f"Variable '{vname}' builds code dynamically "
                      f"($ expansion / embedded LOAD/SQL) - review manually.",
            "raw": vname,
        })
    return script
