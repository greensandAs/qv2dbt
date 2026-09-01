# CoCo Assistant page — Cortex Code Agent SDK with qv2sf-migration skill
# Co-authored with CoCo
import asyncio
import json
import os
import shutil
import tempfile
import streamlit as st
import engine_bridge as eb
import snowflake_utils as sf

_SKILL_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "coco_skill")


def _find_cortex_cli() -> str | None:
    """Find the cortex CLI binary path."""
    env_path = os.environ.get("CORTEX_CODE_CLI_PATH")
    if env_path and os.path.isfile(env_path):
        return env_path
    found = shutil.which("cortex")
    if found:
        return found
    for candidate in [
        os.path.expandvars(r"%LOCALAPPDATA%\cortex\bin\cortex.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\cortex\bin\cortex.cmd"),
        os.path.expandvars(r"%LOCALAPPDATA%\cortex\bin\cortex"),
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\cortex\cortex.exe"),
        os.path.expandvars(r"%APPDATA%\npm\cortex.cmd"),
        os.path.expandvars(r"%USERPROFILE%\.snow\cortex.exe"),
    ]:
        if os.path.isfile(candidate):
            return candidate
    return None


def _export_context(analysis, work_dir: str) -> str:
    """Write a rich migration_context.json for CoCo to read."""
    s = analysis.script
    lin = analysis.lineage

    tables = []
    for t in s.tables:
        fields = []
        for f in t.fields:
            fields.append({
                "name": f.alias,
                "qlikview_expr": f.source_expr,
                "snowflake_sql": f.sf_expr or "",
                "is_passthrough": f.is_passthrough,
                "warnings": list(f.warnings),
            })
        tables.append({
            "name": t.name,
            "layer": t.layer,
            "kind": t.kind.value,
            "source": t.source,
            "fields": fields,
            "joins": [{"kind": j.kind.value, "right_table": j.right_table}
                      for j in t.joins],
            "group_by": t.group_by,
            "where": t.where_raw,
            "warnings": list(t.warnings),
        })

    lineage_cols = []
    for c in lin.columns:
        lineage_cols.append({
            "table": c.table,
            "column": c.column,
            "layer": c.layer,
            "mapping_type": c.mapping_type,
            "qlikview_expr": c.qlik_expr,
            "snowflake_sql": c.snowflake_sql,
            "sources": [{"table": a, "column": b} for a, b in c.ultimate_sources],
            "review_notes": list(c.notes),
        })

    scores = eb.effort_scores(analysis)
    auto = eb.auto_pct(analysis)

    ctx = {
        "script_name": analysis.name,
        "summary": {
            "total_tables": len(s.tables),
            "total_maps": len(s.maps),
            "total_variables": len(s.variables),
            "total_control_blocks": len(s.control_blocks),
            "auto_translate_pct": round(auto, 1),
            "complexity": {
                "low": sum(1 for e in scores if e["Complexity"] == "Low"),
                "medium": sum(1 for e in scores if e["Complexity"] == "Medium"),
                "high": sum(1 for e in scores if e["Complexity"] == "High"),
            },
        },
        "tables": tables,
        "lineage": lineage_cols,
        "effort_scores": scores,
        "sources": [{"id": src.identifier, "kind": src.kind.value,
                     "locator": src.locator} for src in s.sources],
        "maps": [{"name": m.name, "source": m.source, "key": m.key_expr,
                  "value": m.value_expr} for m in s.maps],
        "variables": [{"name": v.name, "value": v.value, "is_let": v.is_let}
                      for v in s.variables],
        "control_blocks": [{"kind": cb.kind, "header": cb.header,
                            "guidance": cb.guidance}
                           for cb in s.control_blocks],
    }

    path = os.path.join(work_dir, "migration_context.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(ctx, fh, indent=2)
    return path


def _get_work_dir(analysis) -> str:
    """Get or create a temp working directory for this analysis session."""
    key = "coco_work_dir"
    if key not in st.session_state or not os.path.isdir(st.session_state[key]):
        d = tempfile.mkdtemp(prefix="qv2dbt_coco_")
        st.session_state[key] = d
    work_dir = st.session_state[key]

    # Copy skill into work dir
    skill_dst = os.path.join(work_dir, "coco_skill")
    if not os.path.isdir(skill_dst):
        shutil.copytree(_SKILL_DIR, skill_dst)

    # Export context if analysis available
    if analysis:
        _export_context(analysis, work_dir)

    return work_dir


def render(session):
    st.header("7 · CoCo Assistant")

    a = st.session_state.get("analysis")

    # Detect SDK
    try:
        from cortex_code_agent_sdk import (
            query as coco_query,
            CortexCodeAgentOptions,
            AssistantMessage,
            ResultMessage,
        )
        from cortex_code_agent_sdk.types import StreamEvent
        _SDK_AVAILABLE = True
    except ImportError:
        _SDK_AVAILABLE = False

    cli_path = _find_cortex_cli()

    if _SDK_AVAILABLE and cli_path:
        mode = "sdk"
        st.caption(
            f"Powered by Cortex Code Agent SDK (CLI: `{cli_path}`). "
            "CoCo has full migration context via the **qv2sf-migration** skill."
        )
    elif session:
        mode = "cortex"
        st.info("CoCo SDK not available — using Cortex COMPLETE fallback.")
        st.caption("Using Snowflake Cortex COMPLETE for migration Q&A.")
    else:
        st.warning("No CoCo SDK or Snowflake connection available.")
        return

    # Context status
    if a:
        work_dir = _get_work_dir(a)
        st.success(f"Context loaded: **{a.name}** — "
                   f"{len(a.script.tables)} tables, "
                   f"{round(eb.auto_pct(a), 0):.0f}% auto-translated")
    else:
        work_dir = None
        st.warning("Upload and parse a script on Page 1 first for full context.")

    # Quick action buttons
    st.markdown("**Quick actions**")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        if st.button("Migration scope", use_container_width=True):
            _dispatch(mode, session, a, cli_path, work_dir,
                      "Read migration_context.json. Summarize the full migration "
                      "scope: how many tables per layer, auto-translation rate, "
                      "complexity breakdown, and key risks.")
    with c2:
        if st.button("Generate DDL + dbt", use_container_width=True):
            _dispatch(mode, session, a, cli_path, work_dir,
                      "Read migration_context.json. For the top 3 highest-complexity "
                      "tables, generate: (1) CREATE TABLE DDL for the RAW landing zone, "
                      "(2) a dbt model with proper source/ref, (3) a reconciliation query.")
    with c3:
        if st.button("Review flagged items", use_container_width=True):
            _dispatch(mode, session, a, cli_path, work_dir,
                      "Read migration_context.json. List ALL columns with review_notes, "
                      "grouped by table. For each, explain the risk and propose the "
                      "correct Snowflake SQL.")
    with c4:
        if st.button("Test queries", use_container_width=True):
            _dispatch(mode, session, a, cli_path, work_dir,
                      "Read migration_context.json. Generate reconciliation SQL "
                      "for every mart-layer table to validate row counts and "
                      "key aggregates match the source.")

    st.divider()

    # Chat history
    for role, text in st.session_state.get("coco_chat", []):
        with st.chat_message(role):
            st.markdown(text)

    # Chat input
    q = st.chat_input("Ask CoCo about your migration...")
    if q:
        _dispatch(mode, session, a, cli_path, work_dir, q)


def _dispatch(mode, session, analysis, cli_path, work_dir, question):
    if mode == "sdk":
        _send_sdk(analysis, question, cli_path, work_dir)
    else:
        _send_cortex(session, analysis, question)


# ---------------------------------------------------------------------------
# Mode 1: CoCo Agent SDK with skill + context file
# ---------------------------------------------------------------------------

def _send_sdk(analysis, question: str, cli_path: str | None, work_dir: str | None):
    from cortex_code_agent_sdk import (
        query as coco_query,
        CortexCodeAgentOptions,
        AssistantMessage,
        ResultMessage,
    )
    from cortex_code_agent_sdk.types import StreamEvent

    st.session_state.setdefault("coco_chat", [])
    st.session_state.coco_chat.append(("user", question))

    with st.chat_message("user"):
        st.markdown(question)

    # Ensure context is fresh
    cwd = work_dir or "."
    if analysis and work_dir:
        _export_context(analysis, work_dir)

    with st.chat_message("assistant"):
        placeholder = st.empty()
        collected = []

        async def _run():
            opts = CortexCodeAgentOptions(
                cwd=cwd,
                include_partial_messages=True,
                max_turns=15,
                allowed_tools=["Read", "Grep", "Glob", "Bash"],
            )
            if cli_path:
                opts.cli_path = cli_path

            # Point to skill directory
            skill_path = os.path.join(cwd, "coco_skill", "SKILL.md")
            prompt_prefix = ""
            if os.path.isfile(skill_path):
                prompt_prefix = (
                    f"[System: Load the skill from {skill_path} and follow "
                    f"its instructions. The migration context is at "
                    f"{os.path.join(cwd, 'migration_context.json')}]\n\n"
                )

            async for message in coco_query(
                prompt=prompt_prefix + question,
                options=opts,
            ):
                if isinstance(message, StreamEvent):
                    event = message.event
                    if event.get("type") == "content_block_delta":
                        delta = event.get("delta", {})
                        if delta.get("type") == "text_delta":
                            collected.append(delta.get("text", ""))
                            placeholder.markdown("".join(collected))
                elif isinstance(message, AssistantMessage):
                    for block in message.content:
                        if hasattr(block, "text") and block.text:
                            if not collected:
                                collected.append(block.text)
                                placeholder.markdown("".join(collected))
                elif isinstance(message, ResultMessage):
                    break

        try:
            import sys
            if sys.platform == "win32":
                asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(_run())
            loop.close()
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            collected.append(f"\n\n**Error:** {e}\n\n```\n{tb}\n```")
            placeholder.markdown("".join(collected))

        answer = "".join(collected) or "(No response from CoCo)"
        st.session_state.coco_chat.append(("assistant", answer))


# ---------------------------------------------------------------------------
# Mode 2: Cortex COMPLETE fallback
# ---------------------------------------------------------------------------

def _send_cortex(session, analysis, question: str):
    st.session_state.setdefault("coco_chat", [])
    st.session_state.coco_chat.append(("user", question))

    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                answer = sf.cortex_chat(
                    session, question, analysis,
                    st.session_state.get("cortex_model", "claude-sonnet-4-6"),
                )
            except Exception as e:
                answer = f"**Error:** {e}"
        st.markdown(answer)
        st.session_state.coco_chat.append(("assistant", answer))
