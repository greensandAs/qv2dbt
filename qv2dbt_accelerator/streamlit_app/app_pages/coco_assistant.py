# CoCo Assistant page — Cortex Code Agent SDK integration for local runs
# Co-authored with CoCo
import asyncio
import streamlit as st
import engine_bridge as eb


def render(session):
    st.header("7 · CoCo Assistant")

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

    if not _SDK_AVAILABLE:
        st.error("Cortex Code Agent SDK not installed.")
        st.code("pip install cortex-code-agent-sdk", language="bash")
        st.caption("The SDK requires the Cortex Code CLI on your PATH. "
                   "Install it first, then restart the app.")
        return

    a = st.session_state.get("analysis")

    st.caption(
        "Powered by the Cortex Code Agent SDK — CoCo can read files, "
        "run commands, execute SQL, and reason about your migration."
    )

    # Quick action buttons
    st.markdown("**Quick actions**")
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("Analyze migration risks", use_container_width=True):
            _send(a, "Analyze the key risks and challenges in this QlikView to "
                  "Snowflake migration. Focus on constructs that may produce "
                  "incorrect results if not carefully reviewed.")
    with col2:
        if st.button("Generate test queries", use_container_width=True):
            _send(a, "Generate reconciliation and validation SQL queries I can "
                  "run to verify the migrated Snowflake tables match the "
                  "original QlikView outputs.")
    with col3:
        if st.button("Explain complex expressions", use_container_width=True):
            _send(a, "Find the most complex QlikView expressions in this script "
                  "and explain what each one does in plain English, then show "
                  "the equivalent Snowflake SQL.")

    st.divider()

    # Chat history
    for role, text in st.session_state.get("coco_chat", []):
        with st.chat_message(role):
            st.markdown(text)

    # Chat input
    q = st.chat_input(
        "Ask CoCo anything about your migration..."
    )
    if q:
        _send(a, q)


def _build_context(analysis) -> str:
    """Build a context string from the parsed analysis for CoCo."""
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


def _send(analysis, question: str):
    """Send a question to CoCo via the Agent SDK and stream the response."""
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
            async for message in coco_query(
                prompt=full_prompt,
                options=CortexCodeAgentOptions(
                    cwd=".",
                    include_partial_messages=True,
                    max_turns=10,
                    allowed_tools=["Read", "Grep", "Glob", "Bash"],
                ),
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
            asyncio.run(_run())
        except Exception as e:
            collected.append(f"\n\n**Error:** {e}")
            placeholder.markdown("".join(collected))

        answer = "".join(collected) or "(No response from CoCo)"
        st.session_state.coco_chat.append(("assistant", answer))
