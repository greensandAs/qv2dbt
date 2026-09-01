"""Generate dbt model SQL from the translated IR.

One dbt model is produced per QlikView table. Source-reading tables become
staging models selecting from ``{{ source(...) }}``; RESIDENT/JOIN-built tables
become intermediate/mart models selecting from ``{{ ref(...) }}``. QlikView's
implicit auto-join on same-named fields is rendered as ``JOIN ... USING (...)``
over the inferred common columns.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..expressions import ExpressionTranslator
from ..models import JoinKind, LoadKind, QvScript, QvTable
from ..utils import case_identifier, snake

import re as _re


def _inline_to_values(source: str | None) -> str:
    """Convert QlikView INLINE [...] data to a Snowflake VALUES clause."""
    if not source:
        return "-- INLINE (no data)"
    # Strip surrounding [ ... ] brackets
    data = source.strip()
    if data.startswith("[") and data.endswith("]"):
        data = data[1:-1].strip()
    lines = [l.strip() for l in data.splitlines() if l.strip()]
    if len(lines) < 2:
        return "-- INLINE (insufficient data)"
    # First line is header
    headers = [h.strip() for h in lines[0].split(",")]
    rows = []
    for line in lines[1:]:
        vals = [v.strip() for v in line.split(",")]
        formatted = []
        for v in vals:
            v = v.strip().strip('"')
            if _re.fullmatch(r"-?\d+(\.\d+)?", v):
                formatted.append(v)
            else:
                formatted.append(f"'{v}'")
        rows.append(f"({', '.join(formatted)})")
    col_list = ", ".join(headers)
    values_list = ",\n           ".join(rows)
    return f"(VALUES\n           {values_list}\n    ) AS t({col_list})"


@dataclass
class ModelFile:
    name: str            # model name = filename without .sql
    layer: str           # staging | intermediate | mart
    sql: str
    columns: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class DbtModelGenerator:
    def __init__(self, config: dict):
        self.config = config
        self.naming = config["naming"]
        self.source_name = self.naming["source_name"]
        self.translator = ExpressionTranslator(config)
        self._model_names: dict[str, str] = {}

    def generate(self, script: QvScript) -> list[ModelFile]:
        self._model_names = {t.name.lower(): self._model_name(t)
                             for t in script.tables}
        return [self._build(t, script) for t in script.tables]

    # -- naming ---------------------------------------------------------------

    def _prefix(self, layer: str) -> str:
        return {"staging": self.naming["staging_prefix"],
                "intermediate": self.naming["intermediate_prefix"],
                "mart": self.naming["mart_prefix"]}.get(layer, "")

    def _model_name(self, table: QvTable) -> str:
        return f"{self._prefix(table.layer)}{snake(table.name)}"

    def _ref_for(self, qv_name: str) -> str:
        mn = self._model_names.get(qv_name.lower())
        if mn:
            return f"{{{{ ref('{mn}') }}}}"
        # Unknown -> treat as a raw source so the model still compiles.
        return f"{{{{ source('{self.source_name}', '{snake(qv_name)}') }}}}"

    # -- model construction ---------------------------------------------------

    def _select_columns(self, table: QvTable) -> tuple[list[str], list[str]]:
        cols, warns = [], []
        for f in table.fields:
            expr = (f.sf_expr or f.source_expr).strip()
            alias = case_identifier(f.alias, self.config["target"]["identifier_case"])
            if f.is_passthrough and expr.strip('"').upper() == alias.upper():
                cols.append(f"    {expr}")
            else:
                cols.append(f"    {expr} as {alias}")
            warns.extend(f.warnings)
        if not cols:
            cols.append("    *")
        return cols, warns

    def _from_clause(self, table: QvTable) -> str:
        if table.kind in (LoadKind.QVD, LoadKind.FILE):
            from ..parser import _source_identifier
            return f"{{{{ source('{self.source_name}', " \
                   f"'{_source_identifier(table.source)}') }}}}"
        if table.kind == LoadKind.SQL:
            return f"{{{{ source('{self.source_name}', '{snake(table.name)}') }}}}"
        if table.kind == LoadKind.RESIDENT:
            if not table.source:
                return "-- SOURCE_PLACEHOLDER (RESIDENT source not resolved)"
            return self._ref_for(table.source)
        if table.kind == LoadKind.INLINE:
            return _inline_to_values(table.source)
        return "-- SOURCE_PLACEHOLDER"

    def _build(self, table: QvTable, script: QvScript) -> ModelFile:
        cols, warns = self._select_columns(table)
        warns = list(dict.fromkeys(warns + table.warnings))
        from_clause = self._from_clause(table)

        header = [
            f"-- Model: {self._model_name(table)}  (layer: {table.layer})",
            f"-- Migrated from QlikView table '{table.name}' "
            f"[{table.kind.value}]",
        ]
        for w in warns:
            header.append(f"-- WARNING: {w}")

        distinct = "distinct\n" if table.distinct else ""
        body = ["with base as (",
                f"    select",
                ("    " + distinct).rstrip() if distinct else None,
                ",\n".join(cols),
                f"    from {from_clause}"]
        body = [b for b in body if b is not None]

        if table.where_sf:
            body.append(f"    where {table.where_sf}")
        if table.group_by:
            gb = ", ".join(self.translator.translate(g)[0]
                           for g in table.group_by)
            body.append(f"    group by {gb}")
        body.append(")")

        # Assemble joins (auto-join on common columns) / concatenation.
        joins_sql, concat_sql = self._join_clauses(table, script)
        final = ["", "select *", "from base"]
        final.extend(joins_sql)
        select_block = "\n".join(final)
        if concat_sql:
            select_block += "\n" + concat_sql

        sql = "\n".join(header) + "\n\n{{ config(materialized='" \
            + ("table" if table.layer == "mart" else "view") + "') }}\n\n" \
            + "\n".join(body) + "\n" + select_block + "\n"

        return ModelFile(name=self._model_name(table), layer=table.layer,
                         sql=sql, columns=[f.alias for f in table.fields],
                         warnings=warns)

    def _join_clauses(self, table: QvTable, script: QvScript):
        joins_sql: list[str] = []
        concat_sql = ""
        n = 0
        for j in table.joins:
            joined = script.table_by_name(j.right_table)
            ref = self._ref_for(j.right_table)
            if j.kind == JoinKind.CONCATENATE:
                concat_sql = f"union all\nselect * from {ref}"
                continue
            n += 1
            alias = f"j{n}"
            keys = self._common_keys(table, joined)
            sqlkw = {JoinKind.LEFT: "left join", JoinKind.RIGHT: "right join",
                     JoinKind.INNER: "inner join", JoinKind.OUTER: "full outer join",
                     JoinKind.KEEP: "inner join"}.get(j.kind, "left join")
            if keys:
                using = ", ".join(case_identifier(
                    k, self.config["target"]["identifier_case"]) for k in keys)
                joins_sql.append(f"{sqlkw} {ref} as {alias} using ({using})")
            else:
                joins_sql.append(
                    f"{sqlkw} {ref} as {alias} "
                    f"-- TODO: specify join keys (no common columns inferred)")
        return joins_sql, concat_sql

    @staticmethod
    def _common_keys(base: QvTable, joined: QvTable | None) -> list[str]:
        if not joined:
            return []
        a = {f.alias.lower(): f.alias for f in base.fields}
        b = {f.alias.lower() for f in joined.fields}
        return [a[k] for k in a if k in b]
