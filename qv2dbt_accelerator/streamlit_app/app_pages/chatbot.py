# Chatbot page — Cortex AI Q&A with full context from the accelerator
# Co-authored with CoCo
import streamlit as st
import engine_bridge as eb
import snowflake_utils as sf


def render(session):
    st.header("6 · Chatbot — Migration Assistant")
    a = st.session_state.get("analysis")
    if not a:
        st.info("Upload and parse a script on page 1 first.")
        return

    st.caption(
        "Ask about your QlikView script, lineage, conversion logic, or get "
        "AI suggestions for hard-to-convert columns."
    )

    # Quick action buttons
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("Summarise migration scope"):
            _ask(session, a, "Summarise the full migration scope: how many tables, "
                 "sources, targets, and what percentage needs manual review?")
    with col2:
        if st.button("List items needing review"):
            _ask(session, a, "List all columns and constructs that need manual review, "
                 "grouped by table.")
    with col3:
        if st.button("Suggest Snowflake SQL for flagged items"):
            # Build a focused prompt for flagged items
            flagged_tables = [
                t for t in a.script.tables
                if any(f.warnings for f in t.fields)
            ]
            if flagged_tables:
                prompt = eb.ai_suggest_prompt(flagged_tables[0], a.lineage)
                _ask(session, a, prompt)
            else:
                st.success("No flagged items — all columns translated cleanly.")

    st.divider()

    # Chat history
    for role, text in st.session_state.get("chat", []):
        with st.chat_message(role):
            st.markdown(text)

    # Chat input
    q = st.chat_input("e.g. Which columns feed sales_fact? How is revenue calculated?")
    if q:
        _ask(session, a, q)


def _ask(session, analysis, question: str):
    """Send question to Cortex and display response."""
    st.session_state.chat.append(("user", question))
    with st.chat_message("user"):
        st.markdown(question)
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                answer = sf.cortex_chat(
                    session, question, analysis,
                    st.session_state.get("cortex_model", "mistral-large2"),
                )
            except Exception as e:
                answer = f"Error calling Cortex: {e}"
        st.markdown(answer)
        st.session_state.chat.append(("assistant", answer))
