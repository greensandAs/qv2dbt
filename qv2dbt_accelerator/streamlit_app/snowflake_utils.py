# Snowflake utility helpers — Cortex AI, persistence, and stage operations
# Co-authored with CoCo
"""
Snowflake helpers for qv2dbt Studio: Cortex chat, analysis persistence to
a Snowflake stage, and catalog operations.
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any

import streamlit as st


# ─── Cortex Chat ──────────────────────────────────────────────────────────────
def cortex_chat(session, question: str, analysis, model: str = "claude-sonnet-4-6") -> str:
    """Send a question to Snowflake Cortex with migration context."""
    context_parts = []

    # Build rich context from the Analysis object
    if hasattr(analysis, "script"):
        # Full Analysis object from accelerator
        tables_info = []
        for t in analysis.script.tables[:20]:
            fields_str = ", ".join(f.alias for f in t.fields[:10])
            tables_info.append(
                f"- {t.name} (layer={t.layer}, kind={t.kind.value}, "
                f"source={t.source or 'n/a'}, fields=[{fields_str}])"
            )
        context_parts.append("## Tables\n" + "\n".join(tables_info))

        # Lineage sample
        lin_rows = []
        for t in analysis.script.tables[:5]:
            for c in analysis.lineage.for_table(t.name)[:5]:
                lin_rows.append(
                    f"- {t.name}.{c.column}: {c.qlik_expr} → {c.snowflake_sql}"
                )
        if lin_rows:
            context_parts.append("## Lineage (sample)\n" + "\n".join(lin_rows))

        # Script excerpt
        context_parts.append(
            "## Script (first 3000 chars)\n```\n" + analysis.text[:3000] + "\n```"
        )
    else:
        # Fallback for dict-style analysis
        context_parts.append(f"Script: {analysis.get('name', 'unknown')}")

    context = "\n\n".join(context_parts)
    prompt = (
        "You are a QlikView-to-Snowflake migration expert. Answer the user's "
        "question using ONLY the context below about their parsed QlikView script. "
        "Give Snowflake SQL examples where helpful. Be concise.\n\n"
        f"{context}\n\nUser question: {question}"
    )

    # Truncate if too long for the model
    if len(prompt) > 12000:
        prompt = prompt[:12000] + "\n...(truncated)"

    try:
        result = session.sql(
            "SELECT SNOWFLAKE.CORTEX.COMPLETE(?, ?) AS response",
            params=[model, prompt],
        ).collect()
        return result[0]["RESPONSE"] if result else "No response from Cortex."
    except Exception as e:
        return f"Cortex unavailable: {e}"


# ─── Persistence: Save/Load Analysis to Stage ─────────────────────────────────
STAGE_NAME = "QV2DBT_STUDIO_STAGE"
STAGE_PATH = f"@{STAGE_NAME}/analyses"


def ensure_stage(session, database: str = None, schema: str = None):
    """Create the internal stage if it doesn't exist."""
    prefix = ""
    if database and schema:
        prefix = f"{database}.{schema}."
    session.sql(
        f"CREATE STAGE IF NOT EXISTS {prefix}{STAGE_NAME} "
        f"COMMENT = 'qv2dbt Studio analysis persistence'"
    ).collect()


def save_analysis(session, analysis, database: str = None, schema: str = None) -> str:
    """Persist analysis metadata to a Snowflake stage. Returns the path."""
    ensure_stage(session, database, schema)

    # Serialize to JSON (script metadata, not the full IR)
    metadata = {
        "name": analysis.name,
        "timestamp": datetime.utcnow().isoformat(),
        "table_count": len(analysis.script.tables),
        "tabs": analysis.tabs,
        "tables": [
            {
                "name": t.name,
                "layer": t.layer,
                "kind": t.kind.value,
                "source": t.source,
                "field_count": len(t.fields),
                "join_count": len(t.joins),
            }
            for t in analysis.script.tables
        ],
        "text": analysis.text,
    }

    filename = f"{analysis.name.replace('.', '_')}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
    prefix = ""
    if database and schema:
        prefix = f"{database}.{schema}."

    # Upload to stage using Snowpark's put_stream (works in SiS and local)
    import io
    json_bytes = json.dumps(metadata).encode("utf-8")
    stream = io.BytesIO(json_bytes)
    stage_path = f"@{prefix}{STAGE_NAME}/analyses/"

    try:
        session.file.put_stream(
            stream, f"{stage_path}{filename}",
            auto_compress=False, overwrite=True
        )
    except (AttributeError, Exception):
        # Fallback: use PUT with /tmp for environments that support it
        import tempfile
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, dir="/tmp"
        )
        json.dump(metadata, tmp)
        tmp.close()
        try:
            session.sql(
                f"PUT 'file://{tmp.name}' {stage_path} "
                f"AUTO_COMPRESS=FALSE OVERWRITE=TRUE"
            ).collect()
        finally:
            os.unlink(tmp.name)

    return f"{stage_path}{filename}"


def list_saved_analyses(session, database: str = None, schema: str = None) -> list[dict]:
    """List previously saved analyses from the stage."""
    prefix = ""
    if database and schema:
        prefix = f"{database}.{schema}."
    try:
        ensure_stage(session, database, schema)
        rows = session.sql(
            f"LIST @{prefix}{STAGE_NAME}/analyses/"
        ).collect()
        return [{"name": r["name"], "size": r["size"], "modified": r["last_modified"]}
                for r in rows]
    except Exception:
        return []


def load_saved_analysis(session, stage_path: str) -> dict | None:
    """Load a saved analysis JSON from stage."""
    import io
    try:
        # Try Snowpark's get_stream (works in SiS)
        stream = session.file.get_stream(stage_path)
        content = stream.read()
        return json.loads(content)
    except (AttributeError, Exception):
        pass
    # Fallback: GET to /tmp
    import tempfile
    tmp_dir = tempfile.mkdtemp(dir="/tmp")
    try:
        session.sql(f"GET '{stage_path}' 'file://{tmp_dir}/'").collect()
        files = os.listdir(tmp_dir)
        if files:
            with open(os.path.join(tmp_dir, files[0])) as f:
                return json.load(f)
    except Exception:
        return None
    return None
