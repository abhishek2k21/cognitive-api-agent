
import streamlit as st
import asyncio
import json
import os
import pandas as pd
from dotenv import load_dotenv
import re

# Load environment variables
load_dotenv()

# Set up logging
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Import from the src directory
from src.api_client import ApiClient
from src.llm_agent import get_cognitive_agent
from src.tools import APIRequest, Question

# --- Page Config ---
st.set_page_config(page_title="Cognitive API Agent", layout="wide")

st.title("🤖 Cognitive API Agent")
st.write("Provide an API endpoint, then chat with the agent. It will ask for details if needed.")

# --- Session State ---
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "Hello! Please provide an API endpoint to begin."}]
if "api_client" not in st.session_state:
    st.session_state.api_client = None
if "api_spec" not in st.session_state:
    st.session_state.api_spec = None
if "pending_api_request" not in st.session_state:
    st.session_state.pending_api_request = None

# --- Helper Functions ---
def add_message(role, content, data=None):
    st.session_state.messages.append({"role": role, "content": content, "data": data})

async def initialize_api_client(url: str):
    st.session_state.api_client = ApiClient(url)
    with st.spinner("Fetching API specification..."):
        spec = await st.session_state.api_client.get_api_spec()
        if spec:
            st.session_state.api_spec = json.dumps(spec, indent=2)
            add_message("assistant", f"✅ API endpoint set to `{url}` and specification loaded successfully! How can I help?")
        else:
            add_message("assistant", f"⚠️ API endpoint set to `{url}`, but I could not find a specification.")
    st.session_state.pending_api_request = None

# --- UI Rendering ---
# (This section remains largely the same but is included for completeness)
if st.session_state.api_client:
    status_message = f"✅ API Endpoint Set: `{st.session_state.api_client.base_url}`"
    if st.session_state.api_spec:
        st.info(status_message + " | ✅ Specification Loaded")
        with st.expander("View Loaded API Specification"):
            st.json(st.session_state.api_spec)
    else:
        st.warning(status_message + " | ⚠️ Specification Not Found")
else:
    st.warning("⚠️ No API endpoint set. Please provide a URL in the chat.")

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("data"):
            if isinstance(msg["data"], list) and msg["data"] and all(isinstance(i, dict) for i in msg["data"]):
                st.dataframe(pd.DataFrame(msg["data"]))
            else:
                st.json(msg["data"])

if st.session_state.pending_api_request:
    with st.container():
        st.warning("Please review the API request below:")
        st.json(st.session_state.pending_api_request.model_dump())
        col1, col2, col3 = st.columns([1, 1, 3])
        with col1:
            if st.button("✅ Execute", use_container_width=True, type="primary"):
                req = st.session_state.pending_api_request
                st.session_state.pending_api_request = None
                with st.spinner("Executing API call..."):
                    result = asyncio.run(st.session_state.api_client.make_request(
                        req.method, req.endpoint, req.json_payload, req.params
                    ))
                add_message("assistant", "API call executed.", data=result)
                st.rerun()
        with col2:
            if st.button("❌ Cancel", use_container_width=True):
                st.session_state.pending_api_request = None
                add_message("assistant", "API request cancelled.")
                st.rerun()

# --- Main Logic ---
if prompt := st.chat_input("Enter a URL or command..."):
    add_message("user", prompt)
    
    url_match = re.search(r'https?://[^\s/]+(?::\d+)?', prompt)
    if url_match:
        asyncio.run(initialize_api_client(url_match.group(0)))
    elif not st.session_state.api_client:
        add_message("assistant", "Please provide an API endpoint first.")
    else:
        with st.spinner("Agent is thinking..."):
            try:
                # Get the last 5 messages for context
                chat_history = json.dumps(st.session_state.messages[-5:])
                agent = get_cognitive_agent(st.session_state.api_spec, chat_history)
                
                # The agent now makes a single, clear decision
                decision = asyncio.run(agent.run(prompt))
                
                # Act based on the type of decision
                if isinstance(decision.data, Question):
                    add_message("assistant", decision.data.question_to_user)
                
                elif isinstance(decision.data, APIRequest):
                    api_request = decision.data
                    if api_request.method in ["POST", "PUT"]:
                        st.session_state.pending_api_request = api_request
                    else: # For GET/DELETE, execute immediately
                        result = asyncio.run(st.session_state.api_client.make_request(
                            api_request.method, api_request.endpoint, api_request.json_payload, api_request.params
                        ))
                        add_message("assistant", "API call successful.", data=result)
                else:
                    add_message("assistant", "I'm not sure how to proceed. Can you please clarify?")

            except Exception as e:
                logger.error(f"An error occurred: {e}", exc_info=True)
                add_message("assistant", f"An error occurred: {e}")
    
    st.rerun()
import asyncio
import streamlit as st
from main import ask_generate, ask_execute

# Set up Streamlit page
st.set_page_config(page_title="Dynamic DB Agent", layout="centered")
st.title("🤖 Dynamic Database Agent")
st.write("You can manage notes (create, update, delete, search) or manage the database structure (create table).")

# Initialize session state for holding the generated SQL
if 'sql_to_execute' not in st.session_state:
    st.session_state.sql_to_execute = ""

# --- User Input ---
placeholder_text = (
    "Try these commands:\n"
    "- 'Create a table named products with an id, a name as text, and a price as numeric.'\n"
    "- 'Update my shopping list to include milk and eggs.'\n"
    "- 'Search for notes about meetings.'"
)
user_input = st.text_area("Enter your command:", placeholder=placeholder_text, height=120)

if st.button("Submit", use_container_width=True):
    if not user_input.strip():
        st.error("Please enter a command.")
    else:
        # Clear previous results before the new run
        st.session_state.sql_to_execute = ""
        with st.spinner("Agent is thinking..."):
            try:
                response = asyncio.run(ask_generate(user_input))

                # Handle DDL: SQL was generated for review
                if response and response.response_type == "ddl_generated":
                    st.info(response.message)
                    st.code(response.sql_query, language="sql")
                    st.session_state.sql_to_execute = response.sql_query

                # Handle DML: Action was performed directly
                elif response and response.response_type == "dml_success":
                    st.success(response.message)
                    if response.note:
                        st.json(response.note)
                    if response.titles:
                        st.json(response.titles)

                # Handle errors
                elif response:
                    st.error(response.message)
                else:
                    st.error("Received an empty response from the agent.")

            except Exception as e:
                st.error(f"An unexpected error occurred: {e}")

# --- Confirmation and Execution Section for DDL ---
if st.session_state.sql_to_execute:
    st.warning("⚠️ Review the SQL command above. Execute it only if it's correct.")
    if st.button("Execute SQL Command", type="primary", use_container_width=True):
        with st.spinner("Executing command..."):
            sql_to_run = st.session_state.sql_to_execute
            st.session_state.sql_to_execute = "" # Clear state immediately

            result = asyncio.run(ask_execute(sql_to_run))
            if result["status"] == "SUCCESS":
                st.success(f"Execution successful: {result['message']}")
            else:
                st.error(f"Execution failed: {result['message']}")

