"""Bridge between the Streamlit UI and the qv2dbt engine.

Provides in-memory analysis (parse -> transform -> lineage), an inventory
summary, per-target conversion (CREATE TABLE / dbt / view / procedure),
a catalog corpus for Cortex, reconciliation SQL, effort scoring, and a ZIP
bundle of a full run.
"""
from __future__ import annotations

import io
import os
import re
import sys
import tempfile
import zipfile
from dataclasses import dataclass, field

# make the qv2dbt package importable when the app runs from streamlit_app/
_PKG_SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
if _PKG_SRC not in sys.path:
    sys.path.insert(0, _PKG_SRC)

from qv2dbt.config import load_config                       # noqa: E402
from qv2dbt.generators.dbt_models import DbtModelGenerator  # noqa: E402
from qv2dbt.generators.sql_views import SqlViewGenerator    # noqa: E402
from qv2dbt.lineage import build_lineage                    # noqa: E402
from qv2dbt.models import LoadKind, QvScript, QvTable       # noqa: E402
from qv2dbt.parser import parse_script, _source_identifier  # noqa: E402
from qv2dbt.pipeline import run_migration                   # noqa: E402
from qv2dbt.qvf_extractor import extract_script, is_binary_qlik  # noqa: E402
from qv2dbt.transformer import Transformer                  # noqa: E402
from qv2dbt.utils import case_identifier, snake, sql_type_guess  # noqa: E402

_TAB = re.compile(r"///\$tab\s*(.*)")
_STORE = re.compile(
    r"(?is)\bstore\b\s+([A-Za-z_][\w ]*?)\s+into\s+(\[[^\]]+\]|'[^']+'|[^\s(;]+)")


@dataclass
class Analysis:
    name: str
    text: str
    config: dict
    script: QvScript
    lineage: object
    tabs: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# analyze
# ---------------------------------------------------------------------------

def analyze(file_bytes: bytes, filename: str, config: dict | None = None
            ) -> Analysis:
    config = config or load_config()
    lower = filename.lower()
    if lower.endswith((".qvf", ".qvw")) or _looks_binary(file_bytes):
        tmp = tempfile.NamedTemporaryFile(suffix=os.path.splitext(lower)[1] or ".qvf",
                                          delete=False)
        tmp.write(file_bytes)
        tmp.close()
        text = extract_script(tmp.name)
    else:
        text = file_bytes.decode("utf-8", errors="replace")

    script = parse_script(text, filename)
    Transformer(config).run(script)
    lineage = build_lineage(script)
    tabs = [m.group(1).strip() for m in _TAB.finditer(text)]
    return Analysis(name=filename, text=text, config=config, script=script,
                    lineage=lineage, tabs=tabs)


def _looks_binary(data: bytes) -> bool:
    head = data[:4096]
    if b"\x00" in head:
        return True
    try:
        head.decode("utf-8")
        return False
    except UnicodeDecodeError:
        return True


# ---------------------------------------------------------------------------
# inventory
# ---------------------------------------------------------------------------

def store_targets(text: str) -> list[dict]:
    out = []
    for m in _STORE.finditer(text):
        tbl, path = m.group(1).strip(), m.group(2).strip().strip("[]'\"")
        kind = "qvd" if path.lower().endswith(".qvd") else "file"
        out.append({"table": tbl, "path": path, "kind": kind})
    return out


def inventory(analysis: Analysis) -> dict:
    s = analysis.script
    src_tables = [t for t in s.tables if t.kind in
                  (LoadKind.QVD, LoadKind.FILE, LoadKind.SQL)]
    resident = [t for t in s.tables if t.kind == LoadKind.RESIDENT]
    marts = [t for t in s.tables if t.layer == "mart"]
    intermediate = [t for t in s.tables if t.layer == "intermediate"]
    staging = [t for t in s.tables if t.layer == "staging"]
    referred_qvds = sorted({t.source for t in s.tables
                            if t.kind == LoadKind.QVD and t.source})
    input_files = sorted({t.source for t in s.tables
                          if t.kind == LoadKind.FILE and t.source})
    outputs = store_targets(analysis.text)
    control = {}
    for cb in s.control_blocks:
        control[cb.kind] = control.get(cb.kind, 0) + 1

    return {
        "counts": {
            "source_tables": len(src_tables),
            "target_tables (marts)": len(marts),
            "staging_tables": len(staging),
            "intermediate_tables": len(intermediate),
            "mapping_tables": len(s.maps),
            "referred_qvds": len(referred_qvds),
            "input_files": len(input_files),
            "output_files_qvds": len(outputs),
            "variables": len(s.variables),
            "control_blocks": len(s.control_blocks),
            "script_tabs": len(analysis.tabs),
        },
        "source_tables": [t.name for t in src_tables],
        "target_tables": [t.name for t in marts],
        "staging_tables": [t.name for t in staging],
        "intermediate_tables": [t.name for t in intermediate],
        "mapping_tables": [m.name for m in s.maps],
        "referred_qvds": referred_qvds,
        "input_files": input_files,
        "output_files_qvds": outputs,
        "variables": [{"name": v.name, "value": v.value} for v in s.variables],
        "control_blocks": control,
        "dependencies": _dependencies(s),
    }


def _dependencies(s: QvScript) -> list[dict]:
    deps = []
    for t in s.tables:
        for j in t.joins:
            deps.append({"from": j.right_table, "to": t.name, "type": j.kind.value})
    return deps


# ---------------------------------------------------------------------------
# conversion (per target)
# ---------------------------------------------------------------------------

def _fqn(name: str, layer: str, config: dict) -> str:
    tgt = config["target"]
    case = tgt["identifier_case"]
    db = case_identifier(tgt["database"], case)
    schema = case_identifier(
        tgt["mart_schema"] if layer == "mart" else tgt["staging_schema"], case)
    prefix = {"staging": config["naming"]["staging_prefix"],
              "intermediate": config["naming"]["intermediate_prefix"],
              "mart": config["naming"]["mart_prefix"]}.get(layer, "")
    obj = case_identifier(f"{prefix}{snake(name)}", case)
    return f"{db}.{schema}.{obj}"


def create_table_ddl(table: QvTable, config: dict) -> str:
    case = config["target"]["identifier_case"]
    fqn = _fqn(table.name, table.layer, config)
    cols = []
    for f in table.fields:
        col = case_identifier(f.alias, case)
        cols.append(f"    {col:<32} {sql_type_guess(f.alias)}")
    body = ",\n".join(cols) if cols else "    -- (no columns inferred)"
    return (f"-- Physical schema for target '{table.name}' [{table.layer}]\n"
            f"create or replace table {fqn} (\n{body}\n);")


def procedure_ddl(table: QvTable, select_sql: str, config: dict) -> str:
    fqn = _fqn(table.name, table.layer, config)
    proc = _fqn(f"build_{table.name}", table.layer, config)
    return (f"-- Stored procedure to (re)build target '{table.name}'\n"
            f"create or replace procedure {proc}()\n"
            f"returns string language sql as\n$$\nbegin\n"
            f"  create or replace table {fqn} as\n{_indent(select_sql)};\n"
            f"  return 'built {fqn}';\nend;\n$$;")


def _indent(sql: str, n: int = 2) -> str:
    pad = " " * n
    return "\n".join(pad + line for line in sql.splitlines())


class _Converter:
    def __init__(self, script: QvScript, config: dict):
        self.script = script
        self.config = config
        self.dbt = DbtModelGenerator(config)
        self.models = {m.name: m for m in self.dbt.generate(script)}
        self.viewer = SqlViewGenerator(config)
        self.viewer._names = {t.name.lower(): self.viewer._view_of(t)
                              for t in script.tables}

    def _model_name(self, t: QvTable) -> str:
        prefix = {"staging": self.config["naming"]["staging_prefix"],
                  "intermediate": self.config["naming"]["intermediate_prefix"],
                  "mart": self.config["naming"]["mart_prefix"]}.get(t.layer, "")
        return f"{prefix}{snake(t.name)}"

    def convert(self, t: QvTable, targets: list[str]) -> dict:
        out = {}
        select_sql = self.viewer._inline_macros(self.viewer._select_sql(t, self.script))
        if "create_table" in targets:
            out["create_table"] = create_table_ddl(t, self.config)
        if "view" in targets:
            fqvn = self.viewer._fqvn(t)
            out["view"] = (f"create or replace view {fqvn} as\n{select_sql}\n;")
        if "dbt" in targets:
            mf = self.models.get(self._model_name(t))
            out["dbt"] = mf.sql if mf else "-- (no dbt model)"
        if "procedure" in targets:
            out["procedure"] = procedure_ddl(t, select_sql, self.config)
        if "select" in targets:
            out["select"] = select_sql + "\n;"
        return out


def converter(analysis: Analysis) -> _Converter:
    return _Converter(analysis.script, analysis.config)


# ---------------------------------------------------------------------------
# catalog corpus (for Cortex Search / RAG) + business text prompt
# ---------------------------------------------------------------------------

def catalog_rows(analysis: Analysis) -> list[dict]:
    """One searchable text record per table (+ its columns) and control block."""
    lin = analysis.lineage
    rows = []
    for t in analysis.script.tables:
        cols = lin.for_table(t.name)
        lines = [f"Table {t.name} (layer={t.layer}, load={t.kind.value}, "
                 f"source={t.source})."]
        for c in cols:
            us = ", ".join(f"{a}.{b}" for a, b in c.ultimate_sources) or "-"
            lines.append(f"Column {c.column} [{c.mapping_type}] = "
                         f"{c.qlik_expr} -> {c.snowflake_sql}; sources: {us}.")
        rows.append({"id": t.name, "type": "table", "layer": t.layer,
                     "text": "\n".join(lines)})
    for i, cb in enumerate(analysis.script.control_blocks, 1):
        rows.append({"id": f"control_{cb.kind}_{i}", "type": "control",
                     "layer": "-",
                     "text": f"Control block {cb.kind} (lines "
                             f"{cb.start_line}-{cb.end_line}): {cb.header}. "
                             f"Guidance: {cb.guidance}"})
    return rows


def catalog_dataframe(analysis: Analysis):
    """One row per target column (+ control blocks) for a durable Snowflake
    catalog table that Cortex Search can index. Columns are upper-cased for
    Snowflake friendliness; TEXT is the searchable blob."""
    import pandas as pd
    lin = analysis.lineage
    rows = []
    for t in analysis.script.tables:
        for c in lin.for_table(t.name):
            st_tables = sorted({a for a, _ in c.ultimate_sources})
            st_cols = [f"{a}.{b}" for a, b in c.ultimate_sources]
            text = (f"Script {analysis.name}. Target {t.name} "
                    f"(layer {t.layer}). Column {c.column} is a "
                    f"{c.mapping_type} mapping. QlikView logic: {c.qlik_expr}. "
                    f"Snowflake SQL: {c.snowflake_sql}. "
                    f"Sources: {', '.join(st_cols) or 'n/a'}. "
                    f"{'Review: ' + '; '.join(c.notes) if c.notes else ''}")
            rows.append({
                "SCRIPT": analysis.name, "OBJECT_TYPE": "column",
                "TABLE_NAME": t.name, "LAYER": t.layer,
                "COLUMN_NAME": c.column, "MAPPING_TYPE": c.mapping_type,
                "SOURCE_TABLES": ", ".join(st_tables),
                "SOURCE_COLUMNS": ", ".join(st_cols),
                "QLIKVIEW_EXPR": c.qlik_expr, "SNOWFLAKE_SQL": c.snowflake_sql,
                "REVIEW_NOTES": "; ".join(c.notes), "TEXT": text,
            })
    for i, cb in enumerate(analysis.script.control_blocks, 1):
        rows.append({
            "SCRIPT": analysis.name, "OBJECT_TYPE": "control",
            "TABLE_NAME": f"{cb.kind}_{i}", "LAYER": "-",
            "COLUMN_NAME": "", "MAPPING_TYPE": cb.kind,
            "SOURCE_TABLES": "", "SOURCE_COLUMNS": "",
            "QLIKVIEW_EXPR": cb.header, "SNOWFLAKE_SQL": "",
            "REVIEW_NOTES": cb.guidance,
            "TEXT": (f"Script {analysis.name}. Control block {cb.kind} "
                     f"(lines {cb.start_line}-{cb.end_line}): {cb.header}. "
                     f"Guidance: {cb.guidance}"),
        })
    return pd.DataFrame(rows)


def cortex_search_setup_sql(db: str, schema: str, table: str, service: str,
                            warehouse: str, target_lag: str = "1 hour") -> str:
    """SQL to (re)create the Cortex Search service over the catalog table.
    The catalog table itself is created by the app when it persists the
    DataFrame; a matching DDL is included for reference."""
    fq_table = f"{db}.{schema}.{table}"
    fq_service = f"{db}.{schema}.{service}"
    return f"""\
-- Reference DDL for the catalog table (the app creates it automatically
-- via write; shown here in case you load it manually):
create table if not exists {fq_table} (
    SCRIPT          varchar,
    OBJECT_TYPE     varchar,
    TABLE_NAME      varchar,
    LAYER           varchar,
    COLUMN_NAME     varchar,
    MAPPING_TYPE    varchar,
    SOURCE_TABLES   varchar,
    SOURCE_COLUMNS  varchar,
    QLIKVIEW_EXPR   varchar,
    SNOWFLAKE_SQL   varchar,
    REVIEW_NOTES    varchar,
    TEXT            varchar
);

-- Cortex Search service over the searchable TEXT column:
create or replace cortex search service {fq_service}
    on TEXT
    attributes SCRIPT, TABLE_NAME, LAYER, MAPPING_TYPE, OBJECT_TYPE
    warehouse = {warehouse}
    target_lag = '{target_lag}'
    as (
        select TEXT, SCRIPT, TABLE_NAME, LAYER, MAPPING_TYPE, OBJECT_TYPE,
               COLUMN_NAME, SOURCE_COLUMNS, QLIKVIEW_EXPR, SNOWFLAKE_SQL
        from {fq_table}
    );
"""


def ai_suggest_prompt(table: QvTable, lineage) -> str:
    """Prompt asking Cortex to propose Snowflake SQL for a table's flagged /
    hard-to-convert constructs."""
    cols = lineage.for_table(table.name)
    flagged = [c for c in cols if c.notes]
    lines = []
    for c in (flagged or cols):
        lines.append(f"- {c.column} [{c.mapping_type}]: QlikView = "
                     f"{c.qlik_expr}; current = {c.snowflake_sql or 'n/a'}; "
                     f"notes = {'; '.join(c.notes) or 'none'}")
    detail = "\n".join(lines)
    return (
        "You are migrating QlikView load-script logic to Snowflake SQL. For "
        "each column below, propose the closest correct Snowflake SQL "
        "expression. Where the QlikView construct is runtime/selection- or "
        "row-order-dependent (e.g. Peek, Previous, Aggr, set analysis), say so "
        "explicitly and give the nearest window-function or subquery approach. "
        "Mark every suggestion as NEEDS REVIEW. Be concise.\n\n"
        f"Table {table.name} (layer {table.layer}):\n{detail}")


def business_prompt(table: QvTable, lineage) -> str:
    cols = lineage.for_table(table.name)
    detail = "\n".join(
        f"- {c.column} [{c.mapping_type}]: {c.qlik_expr}" for c in cols)
    return (
        "In 3-4 sentences, explain the business purpose of this data table for "
        "a business analyst. Be concrete about what it represents and the key "
        "measures/attributes. Avoid technical jargon about SQL.\n\n"
        f"Table: {table.name} (layer: {table.layer})\nColumns and logic:\n{detail}")


def business_summary_fallback(table: QvTable, lineage) -> str:
    cols = lineage.for_table(table.name)
    kinds = {}
    for c in cols:
        kinds[c.mapping_type] = kinds.get(c.mapping_type, 0) + 1
    measures = [c.column for c in cols if c.mapping_type == "aggregate"]
    role = {"mart": "final reporting/analytics target", "staging": "raw ingest",
            "intermediate": "transformation step"}.get(table.layer, "table")
    txt = (f"'{table.name}' is a {role} with {len(cols)} columns "
           f"({', '.join(f'{v} {k}' for k, v in kinds.items())}).")
    if measures:
        txt += f" Key measures: {', '.join(measures)}."
    if table.group_by:
        txt += f" Aggregated by: {', '.join(table.group_by)}."
    return txt + " (Connect Snowflake Cortex for an AI-written description.)"


# ---------------------------------------------------------------------------
# reconciliation + effort
# ---------------------------------------------------------------------------

def reconciliation_sql(table: QvTable, config: dict) -> str:
    tgt_fqn = _fqn(table.name, table.layer, config)
    tgtc = config["target"]
    case = tgtc["identifier_case"]
    db = case_identifier(tgtc["database"], case)
    raw = case_identifier(tgtc["raw_schema"], case)
    if table.kind in (LoadKind.QVD, LoadKind.FILE) and table.source:
        src = f"{db}.{raw}.{case_identifier(_source_identifier(table.source), case)}"
    else:
        src = "-- <original QlikView source / QVD row count>"
    return (f"-- Reconciliation for '{table.name}'\n"
            f"select 'source' as side, count(*) as row_count from {src}\n"
            f"union all\n"
            f"select 'target', count(*) from {tgt_fqn};")


def effort_score(table: QvTable) -> dict:
    reviews = len([w for f in table.fields for w in f.warnings]) + len(table.warnings)
    pts = len(table.fields) * 0.2 + len(table.joins) * 2 + reviews * 3
    if table.group_by:
        pts += 2
    level = "Low" if pts < 5 else "Medium" if pts < 12 else "High"
    return {"table": table.name, "points": round(pts, 1), "complexity": level,
            "review_items": reviews, "joins": len(table.joins),
            "fields": len(table.fields)}


# ---------------------------------------------------------------------------
# full run + zip bundle
# ---------------------------------------------------------------------------

def full_run_zip(file_bytes: bytes, filename: str, config: dict | None = None
                 ) -> bytes:
    """Run the whole pipeline to a temp dir and return a ZIP of all artifacts."""
    tmpin = tempfile.NamedTemporaryFile(
        suffix=os.path.splitext(filename)[1] or ".qvs", delete=False)
    tmpin.write(file_bytes)
    tmpin.close()
    outdir = tempfile.mkdtemp()
    run_migration(tmpin.name, outdir, None)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _dirs, files in os.walk(outdir):
            for f in files:
                full = os.path.join(root, f)
                zf.write(full, os.path.relpath(full, outdir))
    return buf.getvalue()
