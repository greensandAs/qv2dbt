# Production engine bridge integrating the full qv2dbt_accelerator pipeline
# Co-authored with CoCo
"""
Engine bridge for qv2dbt Studio — wraps the full qv2dbt_accelerator package
for parsing, translation, lineage, conversion, and ZIP export.
"""
from __future__ import annotations

import io
import os
import re
import sys
import tempfile
import zipfile
from dataclasses import dataclass, field
from typing import Any, Optional

# Make the qv2dbt package importable:
# 1. In SiS: qv2dbt/ is bundled in the same directory as this file
# 2. Local dev: qv2dbt lives in ../src/
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_PKG_LOCAL = _THIS_DIR  # bundled qv2dbt/ sits here in SiS
_PKG_SRC = os.path.join(os.path.dirname(_THIS_DIR), "src")  # local dev path
for _p in (_PKG_LOCAL, _PKG_SRC):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from qv2dbt.config import load_config
from qv2dbt.generators.dbt_models import DbtModelGenerator
from qv2dbt.generators.sql_views import SqlViewGenerator
from qv2dbt.lineage import build_lineage
from qv2dbt.models import LoadKind, QvScript, QvTable
from qv2dbt.parser import parse_script, _source_identifier
from qv2dbt.pipeline import run_migration
from qv2dbt.qvf_extractor import extract_script, is_binary_qlik, ExtractionError
from qv2dbt.transformer import Transformer
from qv2dbt.utils import case_identifier, snake, sql_type_guess

# ─── Constants ────────────────────────────────────────────────────────────────
MAX_FILE_SIZE_MB = 50
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
SUPPORTED_EXTENSIONS = {".qvs", ".qvf", ".qvw", ".txt"}
_TAB_RE = re.compile(r"///\$tab\s*(.*)")
_STORE_RE = re.compile(
    r"(?is)\bstore\b\s+([A-Za-z_][\w ]*?)\s+into\s+(\[[^\]]+\]|'[^']+'|[^\s(;]+)")


# ─── Errors ──────────────────────────────────────────────────────────────────
class ValidationError(Exception):
    pass


class ParseError(Exception):
    pass


# ─── Data Classes ─────────────────────────────────────────────────────────────
@dataclass
class Analysis:
    name: str
    text: str
    config: dict
    script: QvScript
    lineage: object
    tabs: list[str] = field(default_factory=list)


# ─── Validation ───────────────────────────────────────────────────────────────
def validate_upload(file_bytes: bytes, filename: str) -> None:
    """Validate file before processing. Raises ValidationError on failure."""
    if len(file_bytes) > MAX_FILE_SIZE_BYTES:
        raise ValidationError(
            f"File too large ({len(file_bytes) / 1024 / 1024:.1f} MB). "
            f"Maximum is {MAX_FILE_SIZE_MB} MB."
        )
    if len(file_bytes) == 0:
        raise ValidationError("File is empty.")

    ext = os.path.splitext(filename.lower())[1]
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValidationError(
            f"Unsupported file type '{ext}'. "
            f"Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )


def detect_encoding(file_bytes: bytes) -> str:
    """Detect text encoding, falling back gracefully."""
    if file_bytes[:3] == b"\xef\xbb\xbf":
        return "utf-8-sig"
    try:
        file_bytes[:4096].decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError:
        pass
    try:
        file_bytes[:4096].decode("latin-1")
        return "latin-1"
    except UnicodeDecodeError:
        return "utf-8"


def is_binary(file_bytes: bytes) -> bool:
    """Detect if bytes are a binary Qlik app (vs text script)."""
    if b"\x00" in file_bytes[:4096]:
        return True
    try:
        file_bytes[:4096].decode("utf-8")
        return False
    except UnicodeDecodeError:
        return True


def _extract_script_from_bytes(data: bytes, filename: str) -> str:
    """Extract load script from binary .qvf/.qvw bytes in-memory (no temp files).

    Replicates qvf_extractor.extract_script logic but operates on bytes directly,
    avoiding filesystem writes that may fail in container runtimes.
    """
    import zlib

    TAB_MARKER = "///$tab"
    SCRIPT_TOKENS = (b"LOAD", b"RESIDENT", b"FROM ", b"SQL SELECT", b"///$tab")

    # Find all zlib streams and score them by script-likeness
    results = []
    for m in re.finditer(b"\x78\x9c", data):
        off = m.start()
        try:
            d = zlib.decompressobj().decompress(data[off:])
        except zlib.error:
            continue
        if not d:
            continue
        up = d.upper()
        score = sum(up.count(t.upper()) for t in SCRIPT_TOKENS)
        if score:
            results.append((score, d))

    results.sort(key=lambda t: t[0], reverse=True)

    for _, stream in results:
        text = stream.decode("latin-1", errors="replace")
        idx = text.find(TAB_MARKER)
        if idx == -1:
            m = re.search(r"(?is)\b(SET|LET)\b|\bLOAD\b", text)
            if m is None:
                continue
            idx = max(0, m.start() - 60)
        # Clean: strip binary noise
        cleaned = "".join(
            ch if (ch in "\n\t" or 32 <= ord(ch) < 127) else "" for ch in text[idx:]
        )
        if TAB_MARKER in cleaned or re.search(r"(?is)\bload\b.*\bfrom\b", cleaned):
            # De-duplicate (Qlik stores script copies)
            decl = re.search(
                r"(?m)^\s*\[?([A-Za-z_][\w \-]*?)\]?\s*:\s*(?:\n\s*)?(?:noconcatenate\s+)?LOAD",
                cleaned, re.IGNORECASE)
            if decl:
                name = decl.group(1).strip()
                occ = [mm.start() for mm in re.finditer(
                    r"(?m)^\s*\[?" + re.escape(name) + r"\]?\s*:", cleaned)]
                if len(occ) > 1:
                    cleaned = cleaned[:occ[1]].rstrip()
            return cleaned.rstrip() + "\n"

    raise ParseError(
        f"Could not locate a load script inside '{filename}'. "
        f"The file may be encrypted, section-access protected, or unsupported. "
        f"Export the script from Qlik (Script Editor > Export Script) and "
        f"upload the .qvs file instead."
    )


# ─── Core Analysis ────────────────────────────────────────────────────────────
def analyze(file_bytes: bytes, filename: str,
            config: dict | None = None) -> Analysis:
    """Full analysis: parse → transform → lineage. Raises ParseError on failure."""
    validate_upload(file_bytes, filename)
    config = config or load_config()

    # Extract text from binary or decode text script
    if is_binary(file_bytes):
        try:
            text = _extract_script_from_bytes(file_bytes, filename)
        except Exception as e:
            raise ParseError(
                f"Could not extract script from binary file '{filename}': {e}. "
                f"The file may be encrypted or section-access protected. "
                f"Export the script from Qlik (Script Editor > Export) and "
                f"upload the resulting .qvs instead."
            )
    else:
        encoding = detect_encoding(file_bytes)
        text = file_bytes.decode(encoding, errors="replace")

    if not text.strip():
        raise ParseError("Script is empty after extraction.")

    # Parse and transform
    try:
        script = parse_script(text, filename)
    except Exception as e:
        raise ParseError(f"Parser error: {e}")

    try:
        Transformer(config).run(script)
    except Exception as e:
        raise ParseError(f"Transformer error: {e}")

    lineage = build_lineage(script)
    tabs = [m.group(1).strip() for m in _TAB_RE.finditer(text)]

    return Analysis(name=filename, text=text, config=config,
                    script=script, lineage=lineage, tabs=tabs)


# ─── Inventory ────────────────────────────────────────────────────────────────
def inventory(analysis: Analysis) -> dict:
    """Structured inventory of the parsed script."""
    s = analysis.script
    src_tables = [t for t in s.tables if t.kind in
                  (LoadKind.QVD, LoadKind.FILE, LoadKind.SQL)]
    marts = [t for t in s.tables if t.layer == "mart"]
    intermediate = [t for t in s.tables if t.layer == "intermediate"]
    staging = [t for t in s.tables if t.layer == "staging"]

    outputs = []
    for m in _STORE_RE.finditer(analysis.text):
        tbl, path = m.group(1).strip(), m.group(2).strip().strip("[]'\"")
        kind = "qvd" if path.lower().endswith(".qvd") else "file"
        outputs.append({"table": tbl, "path": path, "kind": kind})

    control = {}
    for cb in s.control_blocks:
        control[cb.kind] = control.get(cb.kind, 0) + 1

    return {
        "counts": {
            "total_tables": len(s.tables),
            "source_tables": len(src_tables),
            "target_tables": len(marts),
            "staging": len(staging),
            "intermediate": len(intermediate),
            "mapping": len(s.maps),
            "variables": len(s.variables),
            "control_blocks": len(s.control_blocks),
            "script_tabs": len(analysis.tabs),
        },
        "tables": [
            {
                "Table": t.name,
                "Layer": t.layer,
                "Load Kind": t.kind.value,
                "Source": t.source or "",
                "Fields": len(t.fields),
                "Joins": len(t.joins),
                "Review Items": len([w for f in t.fields for w in f.warnings]) + len(t.warnings),
            }
            for t in s.tables
        ],
        "variables": [{"name": v.name, "value": v.value} for v in s.variables],
        "control_blocks": control,
        "outputs": outputs,
    }


# ─── Lineage ─────────────────────────────────────────────────────────────────
def lineage_rows(analysis: Analysis) -> list[dict]:
    """Column-level lineage as flat rows for display."""
    rows = []
    for t in analysis.script.tables:
        cols = analysis.lineage.for_table(t.name)
        for c in cols:
            ultimate = ", ".join(f"{a}.{b}" for a, b in c.ultimate_sources) or "-"
            rows.append({
                "Target Table": t.name,
                "Target Column": c.column,
                "Layer": t.layer,
                "Mapping Type": c.mapping_type,
                "QlikView Expression": c.qlik_expr,
                "Snowflake SQL": c.snowflake_sql,
                "Ultimate Sources": ultimate,
                "Needs Review": "Yes" if c.notes else "",
                "Notes": "; ".join(c.notes) if c.notes else "",
            })
    return rows


# ─── Conversion ───────────────────────────────────────────────────────────────
class Converter:
    def __init__(self, analysis: Analysis):
        self.script = analysis.script
        self.config = analysis.config
        self.lineage = analysis.lineage
        self.dbt = DbtModelGenerator(analysis.config)
        self.models = {m.name: m for m in self.dbt.generate(analysis.script)}
        self.viewer = SqlViewGenerator(analysis.config)
        self.viewer._names = {
            t.name.lower(): self.viewer._view_of(t) for t in analysis.script.tables
        }

    def _fqn(self, name: str, layer: str) -> str:
        tgt = self.config["target"]
        case = tgt["identifier_case"]
        db = case_identifier(tgt["database"], case)
        schema = case_identifier(
            tgt["mart_schema"] if layer == "mart" else tgt["staging_schema"], case)
        prefix = {"staging": self.config["naming"]["staging_prefix"],
                  "intermediate": self.config["naming"]["intermediate_prefix"],
                  "mart": self.config["naming"]["mart_prefix"]}.get(layer, "")
        obj = case_identifier(f"{prefix}{snake(name)}", case)
        return f"{db}.{schema}.{obj}"

    def convert(self, table: QvTable, targets: list[str]) -> dict[str, str]:
        """Generate requested output formats for a table."""
        out = {}
        select_sql = self.viewer._inline_macros(
            self.viewer._select_sql(table, self.script))

        if "create_table" in targets:
            case = self.config["target"]["identifier_case"]
            fqn = self._fqn(table.name, table.layer)
            cols = []
            for f in table.fields:
                col = case_identifier(f.alias, case)
                cols.append(f"    {col:<32} {sql_type_guess(f.alias)}")
            body = ",\n".join(cols) if cols else "    -- (no columns)"
            out["create_table"] = (
                f"CREATE OR REPLACE TABLE {fqn} (\n{body}\n);")

        if "view" in targets:
            fqvn = self.viewer._fqvn(table)
            out["view"] = f"CREATE OR REPLACE VIEW {fqvn} AS\n{select_sql}\n;"

        if "dbt" in targets:
            model_name = self._model_name(table)
            mf = self.models.get(model_name)
            out["dbt"] = mf.sql if mf else "-- (no dbt model generated)"

        if "procedure" in targets:
            fqn = self._fqn(table.name, table.layer)
            proc = self._fqn(f"build_{table.name}", table.layer)
            out["procedure"] = (
                f"CREATE OR REPLACE PROCEDURE {proc}()\n"
                f"RETURNS STRING LANGUAGE SQL AS\n$$\nBEGIN\n"
                f"  CREATE OR REPLACE TABLE {fqn} AS\n"
                f"  {select_sql};\n"
                f"  RETURN 'built {fqn}';\nEND;\n$$;")

        if "select" in targets:
            out["select"] = select_sql + "\n;"

        return out

    def _model_name(self, t: QvTable) -> str:
        prefix = {"staging": self.config["naming"]["staging_prefix"],
                  "intermediate": self.config["naming"]["intermediate_prefix"],
                  "mart": self.config["naming"]["mart_prefix"]}.get(t.layer, "")
        return f"{prefix}{snake(t.name)}"

    def convert_all(self, targets: list[str]) -> dict[str, dict[str, str]]:
        """Convert all tables in the script."""
        results = {}
        for t in self.script.tables:
            results[t.name] = self.convert(t, targets)
        return results


# ─── Effort Scoring ───────────────────────────────────────────────────────────
def effort_scores(analysis: Analysis) -> list[dict]:
    """Estimate migration effort per table."""
    scores = []
    for t in analysis.script.tables:
        reviews = len([w for f in t.fields for w in f.warnings]) + len(t.warnings)
        pts = len(t.fields) * 0.2 + len(t.joins) * 2 + reviews * 3
        if t.group_by:
            pts += 2
        level = "Low" if pts < 5 else "Medium" if pts < 12 else "High"
        scores.append({
            "Table": t.name,
            "Layer": t.layer,
            "Fields": len(t.fields),
            "Joins": len(t.joins),
            "Review Items": reviews,
            "Points": round(pts, 1),
            "Complexity": level,
        })
    return scores


# ─── Full Run + ZIP Bundle ────────────────────────────────────────────────────
def full_run_zip(file_bytes: bytes, filename: str,
                 config: dict | None = None) -> bytes:
    """Run the complete pipeline and return a ZIP of all artifacts."""
    validate_upload(file_bytes, filename)

    tmp_in = tempfile.NamedTemporaryFile(
        suffix=os.path.splitext(filename)[1] or ".qvs", delete=False)
    tmp_in.write(file_bytes)
    tmp_in.close()

    outdir = tempfile.mkdtemp()
    try:
        run_migration(tmp_in.name, outdir, None)
    finally:
        os.unlink(tmp_in.name)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _dirs, files in os.walk(outdir):
            for f in files:
                full = os.path.join(root, f)
                zf.write(full, os.path.relpath(full, outdir))
    return buf.getvalue()


# ─── Auto-translatable Percentage ─────────────────────────────────────────────
def auto_pct(analysis: Analysis) -> float:
    """Percentage of fields with no review warnings."""
    total = sum(len(t.fields) for t in analysis.script.tables)
    flagged = sum(
        1 for t in analysis.script.tables
        for f in t.fields if f.warnings
    )
    if total == 0:
        return 100.0
    return ((total - flagged) / total) * 100


# ─── Cortex AI Prompts ────────────────────────────────────────────────────────
def ai_suggest_prompt(table: QvTable, lineage_obj) -> str:
    """Build a prompt for Cortex to suggest SQL for hard-to-convert columns."""
    cols = lineage_obj.for_table(table.name)
    flagged = [c for c in cols if c.notes]
    target = flagged or cols
    lines = []
    for c in target:
        lines.append(
            f"- {c.column} [{c.mapping_type}]: QlikView = {c.qlik_expr}; "
            f"current = {c.snowflake_sql or 'n/a'}; notes = {'; '.join(c.notes) or 'none'}"
        )
    detail = "\n".join(lines)
    return (
        "You are migrating QlikView load-script logic to Snowflake SQL. For "
        "each column below, propose the closest correct Snowflake SQL expression. "
        "Where the construct is runtime/selection-dependent (Peek, Previous, Aggr, "
        "set analysis), say so and give the nearest window-function approach. "
        "Mark every suggestion as NEEDS REVIEW.\n\n"
        f"Table {table.name} (layer {table.layer}):\n{detail}"
    )


def business_prompt(table: QvTable, lineage_obj) -> str:
    """Prompt to generate a business description via Cortex."""
    cols = lineage_obj.for_table(table.name)
    detail = "\n".join(f"- {c.column} [{c.mapping_type}]: {c.qlik_expr}" for c in cols)
    return (
        "In 3-4 sentences, explain the business purpose of this data table for "
        "a business analyst. Be concrete about what it represents.\n\n"
        f"Table: {table.name} (layer: {table.layer})\nColumns:\n{detail}"
    )
