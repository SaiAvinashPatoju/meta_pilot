"""
MetaPilot Chat UI - Streamlit Frontend
Connects to the RAG backend API for campaign assistance.
"""
import streamlit as st
import requests
from typing import Optional
import json

# Configuration
API_BASE_URL = "http://localhost:8000"

# Page config
st.set_page_config(
    page_title="MetaPilot - AI Media Buyer",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for premium look
st.markdown("""
<style>
    .stApp {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
    }
    .main-header {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 2.5rem;
        font-weight: 700;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        color: #a0aec0;
        font-size: 1.1rem;
        margin-bottom: 2rem;
    }
    .chat-message {
        padding: 1rem;
        border-radius: 12px;
        margin-bottom: 1rem;
    }
    .user-message {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
    }
    .assistant-message {
        background: #2d3748;
        color: #e2e8f0;
        border: 1px solid #4a5568;
    }
    .citation-badge {
        background: #4a5568;
        color: #a0aec0;
        padding: 0.2rem 0.5rem;
        border-radius: 4px;
        font-size: 0.8rem;
        margin-right: 0.5rem;
    }
    .source-card {
        background: #2d3748;
        border: 1px solid #4a5568;
        border-radius: 8px;
        padding: 0.8rem;
        margin-top: 0.5rem;
    }
    .stTextInput > div > div > input {
        background: #2d3748;
        color: white;
        border: 1px solid #4a5568;
    }
    .stButton > button {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        border-radius: 8px;
        padding: 0.5rem 2rem;
    }
    .stButton > button:hover {
        background: linear-gradient(90deg, #764ba2 0%, #667eea 100%);
    }
</style>
""", unsafe_allow_html=True)


def check_api_health() -> bool:
    """Check if the API is running."""
    try:
        response = requests.get(f"{API_BASE_URL}/", timeout=5)
        return response.status_code == 200
    except:
        return False


def query_rag(question: str, top_k: int = 4) -> dict:
    """Query the RAG API."""
    try:
        response = requests.post(
            f"{API_BASE_URL}/query",
            json={"query": question, "top_k": top_k},
            timeout=30
        )
        if response.status_code == 200:
            return response.json()
        else:
            return {"error": f"API error: {response.status_code}"}
    except Exception as e:
        return {"error": str(e)}


def ingest_video(youtube_id: str) -> dict:
    """Ingest a YouTube video."""
    try:
        response = requests.post(
            f"{API_BASE_URL}/ingest",
            json={"youtube_id": youtube_id},
            timeout=120
        )
        if response.status_code == 200:
            return response.json()
        else:
            return {"error": f"API error: {response.status_code}"}
    except Exception as e:
        return {"error": str(e)}


def get_rules() -> list:
    """Get playbook rules from API."""
    try:
        response = requests.get(f"{API_BASE_URL}/rules", timeout=10)
        if response.status_code == 200:
            return response.json().get("rules", [])
        return []
    except:
        return []


# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []

if "video_ingested" not in st.session_state:
    st.session_state.video_ingested = False


# Sidebar
with st.sidebar:
    st.markdown("### 🎯 MetaPilot")
    st.markdown("*AI Media Buyer Assistant*")
    st.divider()
    
    # API Status
    api_status = check_api_health()
    if api_status:
        st.success("✅ API Connected")
    else:
        st.error("❌ API Offline - Start the backend server")
        st.code("uvicorn app.main:app --reload", language="bash")
    
    st.divider()
    
    # Video Ingestion
    st.markdown("### 📼 Knowledge Base")
    youtube_id = st.text_input(
        "YouTube Video ID",
        value="t0k4WndiQxk",
        help="Enter the YouTube video ID to ingest"
    )
    
    if st.button("🔄 Ingest Video", disabled=not api_status):
        with st.spinner("Ingesting video..."):
            result = ingest_video(youtube_id)
            if "error" in result:
                st.error(result["error"])
            else:
                st.success(f"✅ Ingested {result.get('chunks_created', 0)} chunks")
                st.session_state.video_ingested = True
    
    st.divider()
    
    # Playbook Rules
    st.markdown("### 📋 Playbook Rules")
    if api_status:
        rules = get_rules()
        if rules:
            for rule in rules[:5]:  # Show first 5 rules
                with st.expander(f"[{rule['id']}] {rule['category']}"):
                    st.write(rule['rule'])
                    st.caption(f"⏱️ {rule['timestamp']}")
        else:
            st.info("No rules loaded yet")
    
    st.divider()
    st.caption("Built with Jim's Digital Marketing methodology")


# Main chat area
st.markdown('<h1 class="main-header">🎯 MetaPilot</h1>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">Your AI-powered Senior Media Buyer trained on Meta Ads best practices</p>', unsafe_allow_html=True)

# Display chat messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        
        # Show citations and sources for assistant messages
        if message["role"] == "assistant" and "citations" in message:
            citations = message["citations"]
            if citations.get("rule_ids") or citations.get("timestamps"):
                st.markdown("---")
                cols = st.columns([1, 3])
                with cols[0]:
                    st.markdown("**📎 Citations:**")
                with cols[1]:
                    citation_text = ""
                    for rule_id in citations.get("rule_ids", []):
                        citation_text += f"`[{rule_id}]` "
                    for ts in citations.get("timestamps", []):
                        citation_text += f"`[{ts}]` "
                    st.markdown(citation_text)

# Chat input
if prompt := st.chat_input("Ask about Meta Ads campaigns...", disabled=not api_status):
    # Add user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    
    # Get AI response
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            result = query_rag(prompt)
            
            if "error" in result:
                response = f"⚠️ Error: {result['error']}"
                citations = {}
            else:
                response = result.get("answer", "I couldn't find an answer.")
                citations = result.get("citations", {})
                
                if result.get("abstained"):
                    st.warning("⚠️ The response was abstained due to lack of grounded sources.")
            
            st.markdown(response)
            
            # Show citations
            if citations.get("rule_ids") or citations.get("timestamps"):
                st.markdown("---")
                cols = st.columns([1, 3])
                with cols[0]:
                    st.markdown("**📎 Citations:**")
                with cols[1]:
                    citation_text = ""
                    for rule_id in citations.get("rule_ids", []):
                        citation_text += f"`[{rule_id}]` "
                    for ts in citations.get("timestamps", []):
                        citation_text += f"`[{ts}]` "
                    st.markdown(citation_text)
            
            # Show sources
            if result.get("sources"):
                with st.expander("📚 Sources"):
                    for i, source in enumerate(result["sources"][:3]):
                        st.markdown(f"**Source {i+1}** - `{source.get('timestamp_str', 'N/A')}`")
                        st.caption(source.get("text", "")[:200] + "...")
    
    # Save assistant message
    st.session_state.messages.append({
        "role": "assistant",
        "content": response,
        "citations": citations
    })

# Welcome message
if not st.session_state.messages:
    st.info("""
    👋 **Welcome to MetaPilot!**
    
    I'm your AI-powered Senior Media Buyer, trained on Jim's Digital Marketing methodology.
    
    **Getting Started:**
    1. Make sure the API backend is running (`uvicorn app.main:app --reload`)
    2. Ingest the course video using the sidebar
    3. Ask me anything about Meta Ads campaigns!
    
    **Example questions:**
    - "What does Jim say about headline length?"
    - "How should I structure my campaign for e-commerce?"
    - "What's the rule for description word count?"
    """)
