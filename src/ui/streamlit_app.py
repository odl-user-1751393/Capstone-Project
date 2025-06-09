import streamlit as st
import asyncio
from app import run_multi_agent
from multi_agent import finalize_approval_and_push

def main():
    if "messages" not in st.session_state:
        st.session_state["messages"] = []
    if "ready_for_approval" not in st.session_state:
        st.session_state["ready_for_approval"] = False

    if st.session_state["ready_for_approval"]:
        approval = st.text_input("Type 'APPROVED' to continue")
        if approval.strip().upper() == "APPROVED":
            finalize_approval_and_push(st.session_state["messages"])
            st.success("Code saved and pushed to GitHub!")
            st.session_state["ready_for_approval"] = False
            st.experimental_rerun()

    else:
        user_input = st.text_input("Enter your request")
        if st.button("Submit") and user_input.strip():
            with st.spinner("Running agents..."):
                result = asyncio.run(run_multi_agent(user_input))
            st.session_state["messages"] = result["messages"]
            st.session_state["ready_for_approval"] = result["ready_for_approval"]

    for msg in st.session_state["messages"]:
        st.markdown(f"**{msg['agent_name']}** ({msg['role']}): {msg['content']}")

if __name__ == "__main__":
    main()
