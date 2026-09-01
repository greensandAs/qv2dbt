# CoCo Assistant page — Cortex Code Agent SDK integration for local runs
# Co-authored with CoCo
import asyncio
import os
import shutil
import streamlit as st
import engine_bridge as eb
import snowflake_utils as sf


def _find_cortex_cli() -> str | None:
    """Find the cortex CLI binary path."""
    # 1. Environment variable override
    env_path = os.environ.get("CORTEX_CODE_CLI_PATH")
    if env_path and os.path.isfile(env_path):
        return env_path
    # 2. Standard PATH lookup
    found = shutil.which("cortex")
    if found:
        return found
    # 3. Common Windows locations
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


def render(session):
    st.header("7 · CoCo Assistant")

    a = st.session_state.get("analysis")

    # Detect SDK availability
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

    # Detect CLI
    cli_path = _find_cortex_cli()

    # Mode selection
    if _SDK_AVAILABLE and cli_path:
        mode = "sdk"
        st.caption(
            f"Powered by Cortex Code Agent SDK (CLI: `{cli_path}`). "
            "CoCo can read files, run commands, execute SQL, and reason "
            "about your migration."
        )
    elif session:
        mode = "cortex"
        if not _SDK_AVAILABLE:
            st.info("CoCo SDK not installed — using Cortex COMPLETE as fallback. "
                    "Install with: `pip install cortex-code-agent-sdk`")
        elif not cli_path:
            st.info("Cortex CLI not found on PATH — using Cortex COMPLETE as "
                    "fallback. Set `CORTEX_CODE_CLI_PATH` to the cortex binary.")
        st.caption("Using Snowflake Cortex COMPLETE for migration Q&A.")
    else:
        st.warning("No CoCo SDK or Snowflake connection available. "
                   "Install the SDK (`pip install cortex-code-agent-sdk`) "
                   "or connect to Snowflake.")
        return

    # Quick action buttons
    st.markdown("**Quick actions**")
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("Analyze migration risks", use_container_width=True):
            _dispatch(mode, session, a, cli_path,
                      "Analyze the key risks and challenges in this QlikView to "
                      "Snowflake migration. Focus on constructs that may produce "
                      "incorrect results if not carefully reviewed.")
    with col2:
        if st.button("Generate test queries", use_container_width=True):
            _dispatch(mode, session, a, cli_path,
                      "Generate reconciliation and validation SQL queries I can "
                      "run to verify the migrated Snowflake tables match the "
                      "original QlikView outputs.")
    with col3:
        if st.button("Explain complex expressions", use_container_width=True):
            _dispatch(mode, session, a, cli_path,
                      "Find the most complex QlikView expressions in this script "
                      "and explain what each one does in plain English, then show "
                      "the equivalent Snowflake SQL.")

    st.divider()

    # Chat history
    for role, text in st.session_state.get("coco_chat", []):
        with st.chat_message(role):
            st.markdown(text)

    # Chat input
    q = st.chat_input("Ask CoCo anything about your migration...")
    if q:
        _dispatch(mode, session, a, cli_path, q)


def _build_context(analysis) -> str:
    """Build a context string from the parsed analysis."""
    if not analysis:
        return ""
    parts = ["You are helping with a QlikView to Snowflake/dbt migration.",
             f"Script: {analysis.name}"]
    s = analysis.script
    parts.append(f"Tables: {len(s.tables)}, Maps: {len(s.maps)}, "
                 f"Variables: {len(s.variables)}, "
                 f"Control blocks: {len(s.control_blocks)}")
    for t in s.tables:
        fields = ", ".join(f.alias for f in t.fields[:15])
        warns = [w for f in t.fields for w in f.warnings]
        line = (f"- {t.name} (layer={t.layer}, kind={t.kind.value}, "
                f"fields=[{fields}])")
        if warns:
            line += f" WARNINGS: {'; '.join(warns[:3])}"
        parts.append(line)
    lin = analysis.lineage
    for c in lin.columns:
        if c.notes:
            parts.append(f"  REVIEW {c.table}.{c.column}: {c.qlik_expr} "
                         f"-> {c.snowflake_sql} | {'; '.join(c.notes)}")
    return "\n".join(parts)


def _dispatch(mode: str, session, analysis, cli_path: str | None,
              question: str):
    """Route to SDK or Cortex COMPLETE based on available mode."""
    if mode == "sdk":
        _send_sdk(analysis, question, cli_path)
    else:
        _send_cortex(session, analysis, question)


# ---------------------------------------------------------------------------
# Mode 1: CoCo Agent SDK (full agent with tools)
# ---------------------------------------------------------------------------

def _send_sdk(analysis, question: str, cli_path: str | None):
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

    context = _build_context(analysis)
    full_prompt = f"{context}\n\nUser question: {question}" if context else question

    with st.chat_message("assistant"):
        placeholder = st.empty()
        collected = []

        async def _run():
            opts = CortexCodeAgentOptions(
                cwd=".",
                include_partial_messages=True,
                max_turns=10,
                allowed_tools=["Read", "Grep", "Glob", "Bash"],
            )
            if cli_path:
                opts.cli_path = cli_path

            async for message in coco_query(
                prompt=full_prompt,
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
            loop = asyncio.new_event_loop()
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
# Mode 2: Cortex COMPLETE fallback (no tools, but always works with SF)
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
