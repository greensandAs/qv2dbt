"""Snowflake + Cortex helpers with auto-detected session and graceful fallback.

Works in three modes, in priority order:
  1. Streamlit-in-Snowflake  -> uses the native active Snowpark session.
  2. Standalone Streamlit     -> connects via snowflake-connector using
     st.secrets["snowflake"] (or environment variables).
  3. No connection            -> every Snowflake/Cortex call returns a clear
     "not connected" result so the app still runs for parsing/conversion.

All Snowflake imports are lazy so this module imports fine with nothing
installed.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Optional

_SESSION: Any = None
_MODE: str = "disconnected"


@dataclass
class SFResult:
    ok: bool
    data: Any = None
    error: str = ""


# ---------------------------------------------------------------------------
# session
# ---------------------------------------------------------------------------

def get_session() -> Any:
    """Return a Snowpark session, or None if unavailable. Cached module-level."""
    global _SESSION, _MODE
    if _SESSION is not None:
        return _SESSION

    # 1) Streamlit in Snowflake
    try:
        from snowflake.snowpark.context import get_active_session
        _SESSION = get_active_session()
        _MODE = "streamlit-in-snowflake"
        return _SESSION
    except Exception:
        pass

    # 2) Standalone via secrets / env
    try:
        cfg = _load_secrets()
        if cfg:
            from snowflake.snowpark import Session
            _SESSION = Session.builder.configs(cfg).create()
            _MODE = "standalone-snowpark"
            return _SESSION
    except Exception:
        pass

    _MODE = "disconnected"
    return None


def connect_with(params: dict) -> SFResult:
    """Explicitly connect using a params dict from the UI."""
    global _SESSION, _MODE
    try:
        from snowflake.snowpark import Session
        _SESSION = Session.builder.configs(
            {k: v for k, v in params.items() if v}).create()
        _MODE = "standalone-snowpark"
        return SFResult(True, data=connection_info())
    except Exception as e:  # pragma: no cover - needs live SF
        return SFResult(False, error=str(e))


def _load_secrets() -> Optional[dict]:
    try:
        import streamlit as st
        if "snowflake" in st.secrets:
            return dict(st.secrets["snowflake"])
    except Exception:
        pass
    keys = ["account", "user", "password", "role", "warehouse", "database",
            "schema", "authenticator"]
    env = {k: os.environ.get(f"SNOWFLAKE_{k.upper()}") for k in keys}
    env = {k: v for k, v in env.items() if v}
    return env or None


def is_connected() -> bool:
    return get_session() is not None


def connection_info() -> dict:
    s = get_session()
    if not s:
        return {"mode": _MODE, "connected": False}
    info = {"mode": _MODE, "connected": True}
    try:
        row = s.sql("select current_account(), current_user(), "
                    "current_role(), current_warehouse(), "
                    "current_database()").collect()[0]
        info.update(account=row[0], user=row[1], role=row[2],
                    warehouse=row[3], database=row[4])
    except Exception:
        pass
    return info


# ---------------------------------------------------------------------------
# SQL execution
# ---------------------------------------------------------------------------

def run_sql(sql: str):
    """Execute SQL, return an SFResult with a pandas DataFrame on success."""
    s = get_session()
    if not s:
        return SFResult(False, error="Not connected to Snowflake.")
    try:
        df = s.sql(sql).to_pandas()
        return SFResult(True, data=df)
    except Exception as e:  # pragma: no cover
        return SFResult(False, error=str(e))


def execute_script(statements: list[str]) -> list[SFResult]:
    """Run multiple statements sequentially (e.g. CREATE VIEW batch)."""
    s = get_session()
    if not s:
        return [SFResult(False, error="Not connected to Snowflake.")]
    out = []
    for stmt in statements:
        stmt = stmt.strip().rstrip(";")
        if not stmt:
            continue
        try:
            s.sql(stmt).collect()
            out.append(SFResult(True, data=stmt[:60]))
        except Exception as e:  # pragma: no cover
            out.append(SFResult(False, error=f"{e}", data=stmt[:60]))
    return out


# ---------------------------------------------------------------------------
# Cortex
# ---------------------------------------------------------------------------

def cortex_available() -> bool:
    return is_connected()


def cortex_complete(prompt: str, model: str = "mistral-large2",
                    temperature: float = 0.2) -> SFResult:
    """Call SNOWFLAKE.CORTEX.COMPLETE. Falls back with a clear message."""
    s = get_session()
    if not s:
        return SFResult(False, error="Cortex needs a Snowflake connection.")
    try:
        # Parameterised to avoid quoting issues in the prompt.
        row = s.sql(
            "select snowflake.cortex.complete(?, ?)", params=[model, prompt]
        ).collect()
        return SFResult(True, data=row[0][0])
    except Exception as e:  # pragma: no cover
        return SFResult(False, error=str(e))


def cortex_search(service_fqn: str, query: str, columns: list[str],
                  limit: int = 5) -> SFResult:
    """Query a Cortex Search service. `service_fqn` = DB.SCHEMA.SERVICE."""
    s = get_session()
    if not s:
        return SFResult(False, error="Cortex Search needs a connection.")
    try:
        from snowflake.core import Root
        root = Root(s)
        db, schema, svc = service_fqn.split(".")
        service = (root.databases[db].schemas[schema]
                   .cortex_search_services[svc])
        resp = service.search(query=query, columns=columns, limit=limit)
        return SFResult(True, data=resp.results)
    except Exception as e:  # pragma: no cover
        return SFResult(False, error=str(e))


def rag_answer(question: str, corpus: list[dict], model: str = "mistral-large2",
               k: int = 6) -> SFResult:
    """RAG-lite fallback when no Cortex Search service exists: local keyword
    retrieval over `corpus` (list of {id, text}) + Cortex COMPLETE."""
    ctx = _keyword_retrieve(question, corpus, k)
    context = "\n\n".join(f"[{c['id']}]\n{c['text']}" for c in ctx)
    prompt = (
        "You are a migration assistant answering questions about a QlikView "
        "load script and its Snowflake/dbt conversion. Use ONLY the context "
        "below; if the answer isn't there, say so.\n\n"
        f"CONTEXT:\n{context}\n\nQUESTION: {question}\n\nANSWER:")
    res = cortex_complete(prompt, model=model)
    if res.ok:
        res.data = {"answer": res.data, "sources": [c["id"] for c in ctx]}
    return res


def _keyword_retrieve(question: str, corpus: list[dict], k: int) -> list[dict]:
    import re
    terms = set(re.findall(r"[A-Za-z_][\w]+", question.lower()))
    scored = []
    for item in corpus:
        text = item.get("text", "").lower()
        score = sum(text.count(t) for t in terms)
        if score:
            scored.append((score, item))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [it for _, it in scored[:k]] or corpus[:k]


def save_dataframe(pdf, fqtn: str, overwrite: bool = True) -> SFResult:
    """Persist a pandas DataFrame to a Snowflake table (auto-create)."""
    s = get_session()
    if not s:
        return SFResult(False, error="Not connected to Snowflake.")
    try:
        sdf = s.create_dataframe(pdf)
        sdf.write.mode("overwrite" if overwrite else "append").save_as_table(fqtn)
        return SFResult(True, data=f"Wrote {len(pdf)} rows to {fqtn}")
    except Exception as e:  # pragma: no cover - needs live SF
        return SFResult(False, error=str(e))


def create_search_service(setup_sql: str) -> list[SFResult]:
    """Run the catalog/search setup SQL (may contain multiple statements)."""
    stmts = [x for x in setup_sql.split(";") if x.strip()]
    return execute_script(stmts)


def mode() -> str:
    get_session()
    return _MODE
