import streamlit as st
import asyncio
import nest_asyncio
import logging
import traceback

from chat import process_message, reset_chat_history
from multi_agent import run_multi_agent, finalize_approval_and_push

nest_asyncio.apply()
logging.basicConfig(level=logging.INFO)

def configure_sidebar():
    if "selected_option" not in st.session_state:
        st.session_state.selected_option = "Multi-Agent"
    if st.sidebar.button("🤖 Multi-Agent"):
        st.session_state.selected_option = "Multi-Agent"
    return st.session_state.selected_option

def render_chat_ui(title, on_submit):
    col1, col2 = st.columns([3, 1])
    with col1:
        st.header(title)
    with col2:
        if st.button("➕ New Chat"):
            if title == "Chat":
                st.session_state.chat_history = []
                reset_chat_history()
            elif title == "Multi-Agent":
                st.session_state.multi_agent_history = []

    st.markdown("""
    <style>
    div[data-testid="stForm"] {
        border: none; 
        padding: 0; 
        box-shadow: none;
    }
    </style>
    """, unsafe_allow_html=True)

    with st.form(key="chat_form", clear_on_submit=True):
        user_input = st.text_input("Message Input", placeholder="Type a message...", key="user_input", label_visibility="collapsed")
        send_clicked = st.form_submit_button("Send")
        if send_clicked:
            on_submit(user_input)

def display_chat_history(chat_history):
    with st.container():
        for chat in chat_history:
            if chat["role"] == "user":
                st.markdown(f"**User**: {chat['message']}")
            else:
                st.markdown(f"**{chat['role']}**: {chat['message']}")

def chat():
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    def on_chat_submit(user_input):
        if user_input:
            try:
                st.session_state.chat_history.append({"role": "user", "message": user_input})
                with st.spinner("Processing your request..."):
                    response = asyncio.run(process_message(user_input))
                st.session_state.chat_history.append({"role": "assistant", "message": response})
            except Exception as e:
                logging.error(f"Error in chat: {e}")
                st.error("Something went wrong.")

    render_chat_ui("Chat", on_chat_submit)
    display_chat_history(st.session_state.chat_history)

def multi_agent():
    if "multi_agent_history" not in st.session_state:
        st.session_state.multi_agent_history = []
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "ready_for_approval" not in st.session_state:
        st.session_state.ready_for_approval = False

    def on_multi_agent_submit(user_input):
        if user_input:
            try:
                st.session_state.multi_agent_history.append({"role": "user", "message": user_input})
                with st.spinner("Agents are collaborating..."):
                    result = asyncio.run(run_multi_agent(user_input))
                st.session_state.messages = result["messages"]
                st.session_state.ready_for_approval = result["ready_for_approval"]
                for msg in result["messages"]:
                    st.session_state.multi_agent_history.append({
                        "role": msg.get("agent_name", msg.get("role", "assistant")),
                        "message": msg.get("content", "[No content]")
                    })
            except Exception as e:
                logging.error(traceback.format_exc())
                st.error(f"Multi-agent error: {str(e)}")

    if st.session_state.ready_for_approval:
        st.markdown("### ✅ Final Output Ready for Review")
    
        for msg in st.session_state.messages:
            st.markdown(f"**{msg.get('agent_name', msg.get('role', 'assistant'))}**: {msg.get('content', '[No content]')}")

        st.divider()

        approval = st.text_input("Type 'APPROVED' to confirm finalization:", key="approval_input")
        if st.button("Submit Decision"):
            if approval.strip().upper() == "APPROVED":
                with st.spinner("Finalizing and pushing code..."):
                    finalize_approval_and_push(st.session_state.messages)
                st.success("✅ Code approved and pushed to GitHub!")
                st.session_state.ready_for_approval = False
                st.experimental_rerun()
            else:
                st.warning("❗Please type 'APPROVED' exactly to confirm.")
    else:
        render_chat_ui("Multi-Agent", on_multi_agent_submit)

    display_chat_history(st.session_state.multi_agent_history)

def main():
    st.set_page_config(page_title="AI Workshop", layout="wide")
    choice = configure_sidebar()
    st.markdown("<h2 style='text-align:center;'>Welcome to the AI Workshop for Developers</h2>", unsafe_allow_html=True)
    if choice == "Multi-Agent":
        multi_agent()
    else:
        chat()  # optionally enable chat later

if __name__ == "__main__":
    main()
