"""Generate plain Snowflake SQL per target: CREATE OR REPLACE VIEW + SELECT.

This is the non-dbt path: fully-resolved physical `database.schema.object`
references (no Jinja), in dependency order, so the conversion can be run
directly in Snowflake or dropped into any orchestrator. One view file per
table, plus a combined build script and SELECT-only variants.
"""
from __future__ import annotations

import os
import re

from ..models import JoinKind, LoadKind, QvScript, QvTable
from ..parser import _source_identifier
from ..utils import case_identifier, snake

_APPLY_MAP = re.compile(
    r'\{\{\s*apply_map\(\s*\'([^\']+)\'\s*,\s*"(.*?)"\s*,\s*"(.*?)"\s*\)\s*\}\}')


class SqlViewGenerator:
    def __init__(self, config: dict):
        self.cfg = config
        tgt = config["target"]
        self.case = tgt["identifier_case"]
        self.db = case_identifier(tgt["database"], self.case)
        self.raw = case_identifier(tgt["raw_schema"], self.case)
        self.stg = case_identifier(tgt["staging_schema"], self.case)
        self.mart = case_identifier(tgt["mart_schema"], self.case)
        self.naming = config["naming"]
        self._names: dict[str, tuple[str, str]] = {}  # tname -> (schema, view)

    # -- naming ---------------------------------------------------------------

    def _prefix(self, layer: str) -> str:
        return {"staging": self.naming["staging_prefix"],
                "intermediate": self.naming["intermediate_prefix"],
                "mart": self.naming["mart_prefix"]}.get(layer, "")

    def _schema_for(self, layer: str) -> str:
        return self.mart if layer == "mart" else self.stg

    def _view_of(self, t: QvTable) -> tuple[str, str]:
        vn = case_identifier(f"{self._prefix(t.layer)}{snake(t.name)}", self.case)
        return (self._schema_for(t.layer), vn)

    def _fqvn(self, t: QvTable) -> str:
        sch, vn = self._view_of(t)
        return f"{self.db}.{sch}.{vn}"

    def _ref(self, qv_name: str) -> str:
        key = qv_name.lower()
        if key in self._names:
            sch, vn = self._names[key]
            return f"{self.db}.{sch}.{vn}"
        # unknown -> assume a raw source table
        return f"{self.db}.{self.raw}.{case_identifier(snake(qv_name), self.case)}"

    # -- from / joins ---------------------------------------------------------

    def _from(self, t: QvTable) -> str:
        if t.kind in (LoadKind.QVD, LoadKind.FILE):
            sid = case_identifier(_source_identifier(t.source or t.name), self.case)
            return f"{self.db}.{self.raw}.{sid}"
        if t.kind == LoadKind.SQL:
            sid = case_identifier(snake(t.name), self.case)
            return f"{self.db}.{self.raw}.{sid}"
        if t.kind == LoadKind.RESIDENT:
            return self._ref(t.source or "")
        if t.kind == LoadKind.INLINE:
            return self._inline_cte(t)
        return f"/* TODO source for {t.name} */"

    def _inline_cte(self, t: QvTable) -> str:
        """Parse INLINE data and generate a VALUES CTE."""
        raw = (t.source or "").strip()
        # INLINE data is enclosed in [...] with rows separated by newlines
        # and columns by commas (or delimiter specified in format)
        content = raw.strip("[]").strip()
        if not content:
            return "/* INLINE: empty data */"
        lines = [l.strip() for l in content.split("\n") if l.strip()]
        if not lines:
            return "/* INLINE: no rows */"

        # Determine column names: from parsed fields, or from first INLINE row.
        col_names = []
        if t.fields and not (len(t.fields) == 1 and t.fields[0].alias == "*"):
            col_names = [case_identifier(f.alias, self.case) for f in t.fields]

        # If first line looks like headers (non-numeric), extract names from it.
        first_parts = [p.strip() for p in lines[0].split(",")]
        data_start = 0
        first_line_is_header = all(
            not re.match(r"^-?\d+(\.\d+)?$", p.strip()) and p.strip()
            for p in first_parts
        )
        if first_line_is_header:
            if not col_names:
                # Use the header line to derive column names
                col_names = [case_identifier(p.strip(), self.case) for p in first_parts]
            data_start = 1
        elif col_names and len(first_parts) == len(col_names):
            # Check if first line matches known column names
            if all(p.strip().strip("'\"").replace(" ", "_").lower() in
                   [c.strip('"').lower() for c in col_names] for p in first_parts):
                data_start = 1

        data_lines = lines[data_start:]
        if not data_lines:
            return "/* INLINE: headers only, no data */"

        # Determine expected column count from headers
        expected_cols = len(col_names) if col_names else None

        rows = []
        for line in data_lines:
            vals = [v.strip() for v in line.split(",")]
            # If row has fewer or more columns than expected, treat the whole
            # line as a single value (handles values containing commas like
            # "1000,000 yen")
            if expected_cols and len(vals) != expected_cols:
                vals = [line.strip()]
            # Quote values appropriately
            quoted = []
            for v in vals:
                v = v.strip()
                if v == "" or v.lower() == "null":
                    quoted.append("NULL")
                elif re.match(r"^-?\d+(\.\d+)?$", v):
                    # Preserve leading zeros as strings (e.g. '00', '01')
                    if len(v) > 1 and v.startswith("0"):
                        quoted.append(f"'{v}'")
                    else:
                        quoted.append(v)
                else:
                    quoted.append(f"'{v}'")
            rows.append(f"({', '.join(quoted)})")
        if not col_names:
            col_names = [f"COL{i+1}" for i in range(len(data_lines[0].split(",")))]
        col_list = ", ".join(col_names)
        return (f"(SELECT * FROM VALUES\n        "
                + "\n        , ".join(rows)
                + f"\n        AS inline_data({col_list}))")

    def _inline_macros(self, expr: str) -> str:
        """Replace the dbt apply_map() macro with an inline correlated
        subquery so the SQL runs outside dbt."""
        def repl(m: re.Match) -> str:
            name, key, default = m.group(1), m.group(2), m.group(3)
            mv = case_identifier(f"map_{snake(name)}", self.case)
            return (f"coalesce((select {case_identifier('mapped_value', self.case)} "
                    f"from {self.db}.{self.stg}.{mv} "
                    f"where {case_identifier('mapped_key', self.case)} = {key} "
                    f"limit 1), {default})")
        return _APPLY_MAP.sub(repl, expr)

    def _cols(self, t: QvTable) -> list[str]:
        out = []
        for f in t.fields:
            expr = self._inline_macros((f.sf_expr or f.source_expr).strip())
            alias = case_identifier(f.alias, self.case)
            if f.is_passthrough and expr.strip('"').upper() == alias.upper():
                out.append(f"    {expr}")
            else:
                out.append(f"    {expr} as {alias}")
        return out or ["    *"]

    @staticmethod
    def _common_keys(base: QvTable, joined: QvTable | None) -> list[str]:
        if not joined:
            return []
        a = {f.alias.lower(): f.alias for f in base.fields}
        b = {f.alias.lower() for f in joined.fields}
        return [a[k] for k in a if k in b]

    def _select_sql(self, t: QvTable, script: QvScript) -> str:
        cols = self._cols(t)
        distinct = "distinct\n    " if t.distinct else ""
        parts = [f"select {distinct}".rstrip(),
                 ",\n".join(cols),
                 f"from {self._from(t)} as base"]
        # joins
        n = 0
        concat = ""
        for j in t.joins:
            joined = script.table_by_name(j.right_table)
            ref = self._ref(j.right_table)
            if j.kind == JoinKind.CONCATENATE:
                concat = f"\nunion all\nselect * from {ref}"
                continue
            n += 1
            kw = {JoinKind.LEFT: "left join", JoinKind.RIGHT: "right join",
                  JoinKind.INNER: "inner join", JoinKind.OUTER: "full outer join",
                  JoinKind.KEEP: "inner join"}.get(j.kind, "left join")
            keys = self._common_keys(t, joined)
            if keys:
                using = ", ".join(case_identifier(k, self.case) for k in keys)
                parts.append(f"{kw} {ref} as j{n} using ({using})")
            else:
                parts.append(f"{kw} {ref} as j{n} "
                             f"/* TODO join keys */")
        # when joins present, wrap base cols as base.* to dedupe via USING
        if n:
            parts = [f"select *",
                     f"from ({self._select_sql_base(t)}) as base"] + parts[3:]
        sql = "\n".join(parts) + concat
        # where / group
        tail = []
        if t.where_sf:
            tail.append(f"where {t.where_sf}")
        if t.group_by:
            from ..expressions import ExpressionTranslator
            tr = ExpressionTranslator(self.cfg)
            gb = ", ".join(tr.translate(g)[0] for g in t.group_by)
            tail.append(f"group by {gb}")
        if tail:
            sql += "\n" + "\n".join(tail)
        return sql

    def _select_sql_base(self, t: QvTable) -> str:
        cols = self._cols(t)
        distinct = "distinct " if t.distinct else ""
        return (f"select {distinct}\n" + ",\n".join(cols) +
                f"\nfrom {self._from(t)}")

    # -- generate -------------------------------------------------------------

    def generate(self, script: QvScript, out_dir: str) -> dict:
        self._names = {t.name.lower(): self._view_of(t) for t in script.tables}
        views_dir = os.path.join(out_dir, "views")
        selects_dir = os.path.join(out_dir, "selects")
        os.makedirs(views_dir, exist_ok=True)
        os.makedirs(selects_dir, exist_ok=True)

        ordered = sorted(script.tables, key=lambda t: t.order)
        combined = [
            "-- ================================================================",
            f"-- Snowflake views generated by qv2dbt from {script.name}",
            "-- Run top-to-bottom (already in dependency order).",
            "-- ================================================================",
            f"create schema if not exists {self.db}.{self.stg};",
            f"create schema if not exists {self.db}.{self.mart};",
            "",
        ]
        for t in ordered:
            sel = self._select_sql(t, script)
            header = (f"-- {t.name}  [{t.layer}]  (from QlikView "
                      f"'{t.kind.value}')")
            ddl = (f"{header}\ncreate or replace view {self._fqvn(t)} as\n"
                   f"{sel}\n;")
            vn = self._view_of(t)[1]
            with open(os.path.join(views_dir, f"{vn}.sql"), "w",
                      encoding="utf-8") as fh:
                fh.write(ddl + "\n")
            with open(os.path.join(selects_dir, f"{vn}.sql"), "w",
                      encoding="utf-8") as fh:
                fh.write(f"{header}\n{sel}\n;\n")
            combined.append(ddl + "\n")

        combined_path = os.path.join(out_dir, "all_views.sql")
        with open(combined_path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(combined) + "\n")

        return {"dir": out_dir, "combined": combined_path,
                "views": views_dir, "selects": selects_dir,
                "count": len(ordered)}


def generate(script: QvScript, config: dict, out_dir: str) -> dict:
    return SqlViewGenerator(config).generate(script, out_dir)
