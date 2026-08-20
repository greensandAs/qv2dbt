"""Column-level lineage engine.

Traces every output column of every table back through RESIDENT refs and JOINs
to the ultimate external source table(s) and column(s), classifies the mapping
type, and captures the business logic (QlikView expression + translated
Snowflake SQL). The resulting :class:`Lineage` object drives the STTM and all
lineage deliverables (JSON graph, Mermaid, HTML explorer).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .models import LoadKind, QvScript, QvTable
from .parser import _source_identifier

# QlikView tokens that are not column references.
_STOP = {
    "as", "resident", "from", "where", "group", "by", "order", "load", "inline",
    "mapping", "distinct", "and", "or", "not", "null", "true", "false", "if",
    "then", "else", "end", "case", "when", "in", "like", "is", "on", "using",
    "asc", "desc", "concatenate", "noconcatenate",
}
_IDENT = re.compile(r'"[^"]+"|\[[^\]]+\]|[A-Za-z_][\w$]*')
_STRLIT = re.compile(r"'[^']*'")
_NUMONLY = re.compile(r"^\d+$")
_AGG = re.compile(r"(?i)\b(sum|count|avg|min|max|only)\s*\(")


def _norm(col: str) -> str:
    return col.strip().strip('"').strip("[]").strip().lower()


def extract_columns(expr: str) -> list[str]:
    """Column identifiers referenced by a QlikView expression."""
    if not expr:
        return []
    s = _STRLIT.sub(" ", expr)                      # drop string literals
    # Drop function-call names: an identifier immediately followed by '('.
    s = re.sub(r'([A-Za-z_][\w$#]*)\s*\(', " ( ", s)
    cols: list[str] = []
    for m in _IDENT.finditer(s):
        tok = m.group(0)
        low = _norm(tok)
        if not low or low in _STOP or _NUMONLY.match(low):
            continue
        raw = tok.strip('"').strip("[]").strip()
        if raw not in cols:
            cols.append(raw)
    return cols


@dataclass
class ColumnDep:
    """A direct upstream dependency of one output column."""

    upstream: str          # upstream table name or "source:<id>"
    column: str
    external: bool         # True when upstream is an external source


@dataclass
class ColumnMap:
    table: str
    column: str
    layer: str
    mapping_type: str                 # direct|derived|aggregate|lookup|constant|join
    qlik_expr: str
    snowflake_sql: str
    direct_deps: list[ColumnDep] = field(default_factory=list)
    ultimate_sources: list[tuple[str, str]] = field(default_factory=list)  # (source, col)
    notes: list[str] = field(default_factory=list)


@dataclass
class Lineage:
    columns: list[ColumnMap] = field(default_factory=list)
    # node metadata: name -> {role, layer}
    tables: dict[str, dict] = field(default_factory=dict)
    sources: dict[str, dict] = field(default_factory=dict)
    # table-level edges (upstream -> downstream)
    table_edges: list[tuple[str, str]] = field(default_factory=list)

    def for_table(self, name: str) -> list[ColumnMap]:
        return [c for c in self.columns if c.table == name]


class LineageBuilder:
    def __init__(self, script: QvScript):
        self.s = script
        self._by_name = {t.name.lower(): t for t in script.tables}
        self._outputs = {t.name.lower(): [f.alias for f in t.fields]
                         for t in script.tables}
        self._map_names = {m.name.lower() for m in script.maps}

    # -- upstream resolution --------------------------------------------------

    def _from_ref(self, t: QvTable):
        """Return (kind, name) describing where the table's rows come from."""
        if t.kind in (LoadKind.QVD, LoadKind.FILE):
            return ("source", _source_identifier(t.source or t.name))
        if t.kind == LoadKind.SQL:
            return ("source", t.name.lower())
        if t.kind == LoadKind.RESIDENT and t.source:
            return ("table", t.source)
        return ("unknown", t.source or "")

    def _join_tables(self, t: QvTable) -> list[str]:
        return [j.right_table for j in t.joins]

    def _provider(self, t: QvTable, col: str):
        """Which upstream provides `col`: returns ColumnDep."""
        low = _norm(col)
        # 1) a joined table that outputs this column
        for jt in self._join_tables(t):
            if low in {_norm(c) for c in self._outputs.get(jt.lower(), [])}:
                return ColumnDep(upstream=jt, column=col, external=False)
        kind, name = self._from_ref(t)
        if kind == "source":
            return ColumnDep(upstream=f"source:{name}", column=col, external=True)
        if kind == "table":
            return ColumnDep(upstream=name, column=col, external=False)
        return ColumnDep(upstream=name or "?", column=col, external=False)

    # -- classification -------------------------------------------------------

    def _classify(self, t: QvTable, f, ids: list[str], is_lookup: bool) -> str:
        expr = f.source_expr.strip()
        if is_lookup:
            return "lookup"
        if not ids:
            return "constant"
        if t.group_by and _AGG.search(f.source_expr):
            return "aggregate"
        # column sourced purely from a joined table
        if f.is_passthrough and len(ids) == 1:
            dep = self._provider(t, ids[0])
            if not dep.external and dep.upstream in self._join_tables(t):
                return "join"
            return "direct"
        return "derived"

    # -- ultimate source resolution ------------------------------------------

    def _ultimate(self, table: str, col: str, seen: set) -> list[tuple[str, str]]:
        key = (table.lower(), _norm(col))
        if key in seen:
            return []
        seen.add(key)
        t = self._by_name.get(table.lower())
        if t is None:
            return []
        # find the field producing `col`
        target = None
        for f in t.fields:
            if _norm(f.alias) == _norm(col):
                target = f
                break
        if target is None:
            # column passes straight through
            dep = self._provider(t, col)
            if dep.external:
                return [(dep.upstream.split("source:")[-1], dep.column)]
            return self._ultimate(dep.upstream, col, seen)
        ids = extract_columns(target.source_expr)
        if not ids:
            return []
        out: list[tuple[str, str]] = []
        for cid in ids:
            dep = self._provider(t, cid)
            if dep.external:
                pair = (dep.upstream.split("source:")[-1], cid)
                if pair not in out:
                    out.append(pair)
            else:
                for p in self._ultimate(dep.upstream, cid, set(seen)):
                    if p not in out:
                        out.append(p)
        return out

    # -- build ----------------------------------------------------------------

    def build(self) -> Lineage:
        lin = Lineage()
        # nodes
        for t in self.s.tables:
            role = t.layer  # staging|intermediate|mart
            lin.tables[t.name] = {"role": role, "layer": role,
                                  "kind": t.kind.value}
        for src in self.s.sources:
            lin.sources[f"source:{src.identifier}"] = {
                "role": "source", "locator": src.locator, "kind": src.kind.value}
        for m in self.s.maps:
            lin.tables[m.name] = {"role": "mapping", "layer": "staging",
                                  "kind": "mapping"}

        table_edges: set[tuple[str, str]] = set()
        for t in self.s.tables:
            for f in t.fields:
                ids = extract_columns(f.source_expr)
                is_lookup = ("apply_map(" in (f.sf_expr or "").lower()
                             or "applymap" in f.source_expr.lower())
                deps: list[ColumnDep] = []
                for cid in ids:
                    dep = self._provider(t, cid)
                    deps.append(dep)
                    up = dep.upstream
                    table_edges.add((up, t.name))
                if is_lookup:
                    # add the mapping table as a lookup provider
                    for m in self.s.maps:
                        if m.name.lower() in f.source_expr.lower():
                            deps.append(ColumnDep(upstream=m.name,
                                                  column="mapped_value",
                                                  external=False))
                            table_edges.add((m.name, t.name))
                cm = ColumnMap(
                    table=t.name, column=f.alias, layer=t.layer,
                    mapping_type=self._classify(t, f, ids, is_lookup),
                    qlik_expr=f.source_expr, snowflake_sql=f.sf_expr or "",
                    direct_deps=deps,
                    ultimate_sources=self._ultimate(t.name, f.alias, set()),
                    notes=list(f.warnings),
                )
                lin.columns.append(cm)
        lin.table_edges = sorted(table_edges)
        return lin


def build_lineage(script: QvScript) -> Lineage:
    return LineageBuilder(script).build()
