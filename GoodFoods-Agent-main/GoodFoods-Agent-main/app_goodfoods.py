from dotenv import load_dotenv
import os
import streamlit as st
import json
from agent.conversation_engine import (
    generate_chat_completion,
    normalize_chat_response,
    execute_tool_calls,
    has_function_simulation
)
from agent.toolkit import restaurant_tools
from agent.prompt_library import (
    restaurant_test_conversation_system_prompt,
    restaurant_test_conversation_system_prompt_w_fewshot,
    restaurant_test_conversation_system_prompt_w_fewshot_1
)

import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('goodfoods')

# Global Constants and Variables
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")

logger.info(f"BASE_DIR set to: {BASE_DIR}")
logger.info(f"DATA_DIR set to: {DATA_DIR}")
load_dotenv()

groq_api_key = os.getenv("GROQ_API_KEY")
if groq_api_key:
    logger.info("Groq API key loaded successfully")
else:
    logger.error("Groq API key not found in environment variables. Add GROQ_API_KEY to your .env file.")
groq_model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
logger.info(f"Groq model set to: {groq_model}")

logger.info("GoodFoods Reservation Assistant started")

st.set_page_config(
    page_title="GoodFoods Reservation Assistant",
    page_icon="🍽️",
    layout="wide",
    initial_sidebar_state="expanded"
)
st.markdown(
    """
    <style>
      .goodfoods-header {
        background: linear-gradient(135deg, #0f172a 0%, #334155 100%);
        padding: 16px 20px;
        border-radius: 12px;
        color: white;
        margin-bottom: 8px;
      }
      .goodfoods-sub { color: #475569; opacity: 0.95; }
      .stButton>button {
        background-color: #334155;
        color: #f8fafc;
        border-radius: 10px;
        border: 1px solid #475569;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05);
        transition: background-color 120ms ease, border-color 120ms ease;
      }
      .stButton>button:hover { background-color: #1f2937; border-color: #475569; }
      .stButton>button:focus-visible { outline: 2px solid #94a3b8; outline-offset: 2px; }
      .stChatMessage { border-radius: 12px; }
    </style>
    """,
    unsafe_allow_html=True,
)
st.markdown(
    '<div class="goodfoods-header"><h2 style="margin:0">GoodFoods Reservation Assistant</h2></div>',
    unsafe_allow_html=True,
)
st.markdown(
    '<p class="goodfoods-sub">Book tables at our restaurants across Bengaluru</p>',
    unsafe_allow_html=True,
)
st.caption("Powered by Agentic AI • Built with Groq + Pydantic Tools and Streamlit :)")

system_prompt = restaurant_test_conversation_system_prompt_w_fewshot_1
welcome_message = (
    "Hello! I'm here to help with your reservation at GoodFoods in Bengaluru. "
    "Ask me for recommendations or book a table at your preferred location."
)

def _build_seed() -> list:
    return [
        {"role": "system", "content": system_prompt},
        {"role": "assistant", "content": welcome_message},
    ]


if "messages" not in st.session_state:
    st.session_state.messages = _build_seed()

def reset_conversation():
    logger.info("Conversation reset by user")
    st.session_state.messages = _build_seed()

with st.sidebar:
    st.button("Restart Conversation", on_click=reset_conversation)
    st.markdown("---")
    st.markdown(f"**Model:** `{groq_model}`")
    st.markdown("Change via `GROQ_MODEL` in your `.env` file.")

for message in st.session_state.messages:
    if message["role"] not in ["system", "tool"]:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

if prompt := st.chat_input("Ask about reservations or available restaurants..."):
    logger.info(f"User input received: {prompt}...")

    # Add user message to history
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        # Live agent trace (collapsible, open by default)
        trace_expander = st.expander("Agent thinking & tool activity (live)", expanded=True)
        with trace_expander:
            st.markdown("**Request received** — preparing a plan…")
            trace_plan_placeholder = st.empty()
            trace_toolcalls_placeholder = st.empty()
            trace_toolresults_placeholder = st.empty()
            trace_followup_placeholder = st.empty()

        with st.spinner("Thinking..."):
            try:
                logger.info(
                    f"Making Groq API call with conversation history length: "
                    f"{len(st.session_state.messages)} messages"
                )
                api_response = generate_chat_completion(
                    api_key=groq_api_key,
                    conversation_history=st.session_state.messages,
                    tools=restaurant_tools,
                    model_type=groq_model,
                    tool_calling_enabled=True,
                )
            except Exception as e:
                logger.error(f"Groq API call failed: {str(e)}", exc_info=True)
                st.error(
                    "An error occurred with the API call. "
                    "Please check your GROQ_API_KEY and restart the conversation."
                )
                st.stop()

        formatted_response = normalize_chat_response(api_response)
        logger.info(f"API response received: {type(formatted_response)}")

        try:
            assistant_msg = api_response.choices[0].message
        except Exception:
            assistant_msg = None

        # Show plan + planned tool calls in trace
        with trace_expander:
            if assistant_msg and (assistant_msg.content or "").strip():
                trace_plan_placeholder.markdown(
                    f"**Assistant plan**\n\n{assistant_msg.content}"
                )
            if assistant_msg and assistant_msg.tool_calls:
                tool_summaries = []
                for tc in assistant_msg.tool_calls:
                    args_preview = tc.function.arguments
                    if isinstance(args_preview, str) and len(args_preview) > 600:
                        args_preview = args_preview[:600] + "…"
                    tool_summaries.append(
                        f"- `{tc.function.name}` with args: `{args_preview}`"
                    )
                if tool_summaries:
                    trace_toolcalls_placeholder.markdown(
                        "**Planned tool calls**\n\n" + "\n".join(tool_summaries)
                    )

        if not isinstance(formatted_response, list):
            response_content = formatted_response.get("content", "")

            if has_function_simulation(response_content):
                logger.warning(
                    f"Function simulation detected: {response_content[:100]}..."
                )
                st.error(
                    "An error occurred processing your request. "
                    "Please restart the conversation."
                )
                st.stop()
            else:
                st.markdown(response_content)
                st.session_state.messages.append(formatted_response)

        if isinstance(formatted_response, list):
            logger.info(f"Processing {len(formatted_response)} tool call(s)")
            message_placeholder = st.empty()
            message_placeholder.markdown("Finding the best options for you...")

            # IMPORTANT: append the assistant message that contains tool_calls FIRST
            try:
                assistant_msg_dict = {
                    "role": "assistant",
                    "content": assistant_msg.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in (assistant_msg.tool_calls or [])
                    ],
                }
                st.session_state.messages.append(assistant_msg_dict)
            except Exception as e:
                logger.error(
                    f"Failed to append assistant tool_calls message: {str(e)}",
                    exc_info=True,
                )

            # Execute tools and collect results
            tool_messages = execute_tool_calls(formatted_response)
            st.session_state.messages.extend(tool_messages)

            # Update trace with tool results
            with trace_expander:
                try:
                    rendered = []
                    for tm in tool_messages:
                        name = tm.get("name", "tool")
                        content = tm.get("content", "")
                        preview = content
                        if isinstance(preview, str) and len(preview) > 600:
                            preview = preview[:600] + "…"
                        rendered.append(f"- `{name}` result: `{preview}`")
                    if rendered:
                        trace_toolresults_placeholder.markdown(
                            "**Tool results**\n\n" + "\n".join(rendered)
                        )
                except Exception as e:
                    logger.error(f"Failed to render tool results in trace: {e}")

            logger.info(f"Tool execution completed with {len(tool_messages)} result(s)")
            try:
                updated_response = generate_chat_completion(
                    api_key=groq_api_key,
                    conversation_history=st.session_state.messages,
                    tools=restaurant_tools,
                    model_type=groq_model,
                    tool_calling_enabled=False,
                )
            except Exception as e:
                logger.error(f"Groq follow-up API call failed: {str(e)}", exc_info=True)
                st.error(
                    "An error occurred processing tool results. "
                    "Please restart the conversation."
                )
                st.stop()

            # Display final response
            formatted_updated_response = normalize_chat_response(updated_response)
            message_placeholder.markdown(formatted_updated_response.get("content", ""))
            st.session_state.messages.append(formatted_updated_response)

            # Update trace with follow-up
            with trace_expander:
                trace_followup_placeholder.markdown("Response delivered.")