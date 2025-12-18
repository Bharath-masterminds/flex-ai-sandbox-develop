# streamlit_opsresolve.py  
import sys
from pathlib import Path
# Ensure workspace root is in sys.path for local imports
workspace_root = Path(__file__).parent.parent.parent
if str(workspace_root) not in sys.path:
    sys.path.insert(0, str(workspace_root))

import asyncio  
from typing import Any, List  
  
import streamlit as st  
  
from dotenv import load_dotenv  

# Load environment variables BEFORE importing IoC components
# This ensures DEPLOYMENT_FLAVOR is available when OpsResolveIocConfig validates
load_dotenv()

from phoenix_setup import setup_phoenix_tracing  
  
from use_cases.ops_resolve.ioc.ops_resolve_composition_root import OpsResolveCompositionRoot
from use_cases.ops_resolve.ops_resolve_supervisor import OpsResolveSupervisor  


@st.cache_resource
def get_ioc_container():
    """
    Create and cache the IoC container to ensure singletons work across Streamlit reruns.
    This prevents the container from being recreated on every Streamlit interaction.
    
    IMPORTANT: Returns a DynamicContainer instance (not OpsResolveCompositionRoot).
    Type hint removed to avoid confusion - dependency_injector returns DynamicContainer.
    """
    setup_phoenix_tracing("ops-resolve-streamlit")
    container = OpsResolveCompositionRoot()
    return container
  
  
async def build_supervisor() -> OpsResolveSupervisor:  
    """
    Build the supervisor by retrieving it from the IoC container.
    
    CRITICAL - November 2024:
    This function MUST be async because container.get_supervisor() returns a coroutine.
    
    ISSUE HISTORY:
    - Original error: 'DynamicContainer' object has no attribute 'get_supervisor'
    - First attempt: Used asyncio.run(container.get_supervisor()) - still failed
    - Root cause: get_supervisor was an instance method, not a provider
    - Solution: Converted get_supervisor to providers.Callable in composition_root.py
    
    USAGE PATTERN:
    - container.get_supervisor() returns a coroutine (not the supervisor itself)
    - Must await the coroutine: supervisor = await container.get_supervisor()
    - In synchronous context, use: asyncio.run(build_supervisor())
    """
    container = get_ioc_container()
    supervisor = await container.get_supervisor()
    return supervisor  
  
  
def _content_to_text(content: Any) -> str:  
    """  
    Normalize message.content to a string. LangChain sometimes returns a list of parts.  
    """  
    if content is None:  
        return ""  
    if isinstance(content, str):  
        return content  
    if isinstance(content, list):  
        out: List[str] = []  
        for part in content:  
            if isinstance(part, dict):  
                # common shapes: {"type": "text", "text": "..."}  
                if "text" in part:  
                    out.append(str(part["text"]))  
                elif "content" in part:  
                    out.append(str(part["content"]))  
                else:  
                    out.append(str(part))  
            else:  
                out.append(str(part))  
        return "".join(out)  
    return str(content)  
  
  
def stream_agent_and_render(supervisor: OpsResolveSupervisor, query: str, live_log_ph, final_md_ph):  
    """  
    Stream directly from supervisor.app.stream and render:  
      - A readable live log (no pretty repr)  
      - The current/last AI response as Markdown  
    """  
    from langchain_core.messages import convert_to_messages  
  
    stream_generator = supervisor.app.stream({"messages": [{"role": "user", "content": query}]})  
  
    log_lines: List[str] = []  
    last_ai_md: str = ""  
  
    for update in stream_generator:  
        # update is a dict of node_name -> node_update  
        for node_name, node_update in update.items():  
            messages = convert_to_messages(node_update["messages"]) or []  
            if not messages:  
                continue  
  
            # only display the last message for the node update (like your pretty_print code)  
            m = messages[-1]  
            role = getattr(m, "type", getattr(m, "role", "unknown"))  
            content_text = _content_to_text(getattr(m, "content", ""))  
  
            # Keep a readable log line (don’t dump HTML/ANSI)  
            short_preview = (content_text[:300] + "…") if len(content_text) > 300 else content_text  
            log_lines.append(f"- {node_name} [{role}]: {short_preview}")  
            live_log_ph.markdown("\n".join(log_lines))  
  
            # If it's the assistant/AI, render as Markdown (this is the main business-facing output)  
            if role in ("ai", "assistant"):  
                last_ai_md = content_text  
                final_md_ph.markdown(last_ai_md)  
  
    return last_ai_md  
  
  
def main():  
    st.set_page_config(
        page_title="OpsResolve RCA", 
        page_icon="🛠️", 
        layout="centered",
        menu_items={
            'Get Help': None,
            'Report a bug': None,
            'About': None
        }
    )
    
    # Hide Streamlit deploy button and menu items
    st.markdown("""
        <style>
            .reportview-container .main .block-container{{
                padding-top: 1rem;
            }}
            #MainMenu {visibility: hidden !important;}
            .stDeployButton {display: none !important;}
            .stActionButton {display: none !important;}
            footer {visibility: hidden !important;}
            header[data-testid="stHeader"] {display: none !important;}
            .stToolbar {display: none !important;}
            div[data-testid="stToolbar"] {display: none !important;}
        </style>
        """, unsafe_allow_html=True)
    
    # Get IoC container and check authentication
    container = get_ioc_container()
    azure_auth = container.get_azure_auth()
    
    # Check authentication - will stop execution if not authenticated
    if not azure_auth.check_authentication():
        return
    
    st.title("🛠️ OpsResolve: Incident RCA")  
    st.caption("Enter an incident number to stream the agent's analysis.")  
  
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        # User info and logout
        azure_auth.show_user_info_sidebar()
        
        st.divider()
        
        default_incident = st.text_input("Default Incident ID", value="INC43951297")
  
    incident_id = st.text_input(
        "Incident ID", 
        value=default_incident, 
        help="Enter the incident ID to analyze (e.g., INC43951297)"
    )  
    run_btn = st.button("🔍 Analyze Incident", type="primary")  
  
    # UI placeholders  
    final_header = st.subheader("📊 Final Analysis")  
    final_md_ph = st.empty()  
  
    with st.expander("🔧 Live updates (technical)", expanded=False):  
        live_log_ph = st.empty()  
  
    if run_btn:  
        if not incident_id.strip():  
            st.error("Please enter a valid incident ID.")  
            st.stop()  
  
        with st.status(f"Running analysis for {incident_id}...", expanded=True) as status:  
            try:  
                # CRITICAL: Use asyncio.run() because build_supervisor() is async
                # build_supervisor() must await container.get_supervisor() which returns a coroutine
                # Cannot use await here because main() is synchronous (Streamlit requirement)
                supervisor = asyncio.run(build_supervisor())  
                query = (  
                    f"Please analyze incident {incident_id} to identify root cause with supporting "  
                    f"evidence and provide resolution steps."  
                )  
                final_answer = stream_agent_and_render(supervisor, query, live_log_ph, final_md_ph)  
  
                # If nothing arrived as an AI message, give a helpful note  
                if not final_answer.strip():  
                    final_md_ph.info("No AI response captured. Check the Live updates above for details.")  
  
                status.update(label="✅ Analysis complete", state="complete", expanded=False)  
            except Exception as e:  
                status.update(label="❌ Analysis failed", state="error", expanded=True)  
                st.error(f"Error during analysis: {e}")  
  
  
if __name__ == "__main__":  
    main()