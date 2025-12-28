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
    .progress-bar {
        background: #2d3748;
        border-radius: 10px;
        height: 20px;
        margin: 1rem 0;
    }
    .progress-fill {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        height: 100%;
        border-radius: 10px;
        transition: width 0.3s ease;
    }
    .pillar-badge {
        display: inline-block;
        padding: 0.3rem 0.8rem;
        border-radius: 20px;
        margin: 0.2rem;
        font-size: 0.85rem;
    }
    .pillar-complete {
        background: #48bb78;
        color: white;
    }
    .pillar-pending {
        background: #4a5568;
        color: #a0aec0;
    }
    .citation-badge {
        background: #4a5568;
        color: #a0aec0;
        padding: 0.2rem 0.5rem;
        border-radius: 4px;
        font-size: 0.8rem;
        margin-right: 0.5rem;
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


def create_agent_session() -> Optional[dict]:
    """Create a new agent session."""
    try:
        response = requests.post(f"{API_BASE_URL}/agent/session", timeout=10)
        if response.status_code == 200:
            return response.json()
        return None
    except:
        return None


def agent_chat(session_id: str, message: str) -> dict:
    """Chat with the agent."""
    try:
        response = requests.post(
            f"{API_BASE_URL}/agent/chat",
            json={"session_id": session_id, "message": message},
            timeout=30
        )
        if response.status_code == 200:
            return response.json()
        return {"error": f"API error: {response.status_code}"}
    except Exception as e:
        return {"error": str(e)}


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


def generate_full_ad(product_name: str, usp: str, target_audience: str = None) -> dict:
    """Generate complete ad creative."""
    try:
        response = requests.post(
            f"{API_BASE_URL}/creative/full-ad",
            json={
                "product_name": product_name,
                "usp": usp,
                "target_audience": target_audience
            },
            timeout=60
        )
        if response.status_code == 200:
            return response.json()
        return {"error": f"API error: {response.status_code}"}
    except Exception as e:
        return {"error": str(e)}


# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "agent_session_id" not in st.session_state:
    st.session_state.agent_session_id = None
if "agent_messages" not in st.session_state:
    st.session_state.agent_messages = []
if "requirements" not in st.session_state:
    st.session_state.requirements = {}
if "progress" not in st.session_state:
    st.session_state.progress = 0
if "generated_creative" not in st.session_state:
    st.session_state.generated_creative = None


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
        st.error("❌ API Offline")
        st.code("uvicorn app.main:app --reload", language="bash")
    
    st.divider()
    
    # Video Ingestion
    st.markdown("### 📼 Knowledge Base")
    youtube_id = st.text_input(
        "YouTube Video ID",
        value="t0k4WndiQxk",
        help="Enter the YouTube video ID"
    )
    
    if st.button("🔄 Ingest Video", disabled=not api_status):
        with st.spinner("Ingesting..."):
            result = ingest_video(youtube_id)
            if "error" in result:
                st.error(result["error"])
            else:
                st.success(f"✅ {result.get('chunks_created', 0)} chunks")
    
    st.divider()
    
    # Playbook Rules
    st.markdown("### 📋 Rules Preview")
    if api_status:
        rules = get_rules()
        if rules:
            for rule in rules[:3]:
                with st.expander(f"[{rule['id']}]"):
                    st.write(rule['rule'])
    
    st.divider()
    st.caption("Jim's Digital Marketing Methodology")


# Main content
st.markdown('<h1 class="main-header">🎯 MetaPilot</h1>', unsafe_allow_html=True)

# Mode tabs
tab1, tab2, tab3 = st.tabs(["💬 Campaign Builder", "✍️ Creative Studio", "🔍 Knowledge Q&A"])

# ========== TAB 1: Campaign Builder (Agent Mode) ==========
with tab1:
    st.markdown("*Build your Meta Ads campaign with guided assistance*")
    
    # Progress tracker
    if st.session_state.progress > 0:
        st.markdown(f"**Campaign Progress: {st.session_state.progress}%**")
        st.progress(st.session_state.progress / 100)
        
        # Pillar badges
        pillars = ["objective", "budget", "targeting", "usp", "product_name"]
        missing = st.session_state.requirements.get("missing_pillars", pillars)
        cols = st.columns(5)
        for i, pillar in enumerate(pillars):
            with cols[i]:
                if pillar not in missing:
                    st.markdown(f"✅ {pillar.replace('_', ' ').title()}")
                else:
                    st.markdown(f"⏳ {pillar.replace('_', ' ').title()}")
    
    # Start new session button
    if not st.session_state.agent_session_id:
        if st.button("🚀 Start Campaign Builder", disabled=not api_status, use_container_width=True):
            session = create_agent_session()
            if session:
                st.session_state.agent_session_id = session["session_id"]
                st.session_state.agent_messages = [
                    {"role": "assistant", "content": session["welcome_message"]}
                ]
                st.rerun()
    else:
        # Reset button
        if st.button("🔄 Start New Campaign", use_container_width=True):
            st.session_state.agent_session_id = None
            st.session_state.agent_messages = []
            st.session_state.requirements = {}
            st.session_state.progress = 0
            st.rerun()
    
    # Display agent messages
    for msg in st.session_state.agent_messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
    
    # Chat input for agent
    if st.session_state.agent_session_id:
        if prompt := st.chat_input("Tell me about your product...", key="agent_input"):
            # Add user message
            st.session_state.agent_messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)
            
            # Get agent response
            with st.chat_message("assistant"):
                with st.spinner("Thinking..."):
                    result = agent_chat(st.session_state.agent_session_id, prompt)
                    
                    if "error" in result:
                        response = f"⚠️ Error: {result['error']}"
                    else:
                        response = result.get("response", "...")
                        st.session_state.progress = result.get("progress", 0)
                        st.session_state.requirements = result
                    
                    st.markdown(response)
            
            st.session_state.agent_messages.append({"role": "assistant", "content": response})
            st.rerun()


# ========== TAB 2: Creative Studio ==========
with tab2:
    st.markdown("*Generate ad copy following Jim's copywriting rules*")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("### 📝 Input")
        product_name = st.text_input("Product/Service Name", placeholder="e.g., Organic Coffee")
        usp = st.text_area("Unique Selling Proposition", placeholder="What makes it unique?", height=100)
        target_audience = st.text_input("Target Audience (optional)", placeholder="e.g., Coffee lovers in NYC")
        
        if st.button("✨ Generate Ad Copy", disabled=not api_status or not product_name or not usp, use_container_width=True):
            with st.spinner("Generating creative..."):
                result = generate_full_ad(product_name, usp, target_audience)
                if "error" not in result:
                    st.session_state.generated_creative = result
                else:
                    st.error(result["error"])
    
    with col2:
        st.markdown("### 🎨 Generated Creative")
        
        if st.session_state.generated_creative:
            creative = st.session_state.generated_creative
            
            # Headlines
            st.markdown("**Headlines** `[COPY-001]`")
            for i, h in enumerate(creative.get("headlines", {}).get("headlines", [])[:3]):
                st.code(h, language=None)
            
            st.divider()
            
            # Descriptions
            st.markdown("**Descriptions** `[COPY-002]` (<5 words)")
            for d in creative.get("descriptions", {}).get("descriptions", [])[:3]:
                st.code(d, language=None)
            
            st.divider()
            
            # Primary Text
            st.markdown("**Primary Text** `[COPY-004]` (PAS Framework)")
            variations = creative.get("primary_text", {}).get("variations", [])
            if variations:
                with st.expander("View Primary Text", expanded=True):
                    st.markdown(variations[0])
            
            # Rule citations
            st.markdown("---")
            citations = creative.get("rule_citations", [])
            st.markdown(f"📎 Rules applied: {' '.join([f'`[{c}]`' for c in citations])}")
        else:
            st.info("Fill in the form and click 'Generate Ad Copy' to create headlines, descriptions, and primary text.")


# ========== TAB 3: Knowledge Q&A (RAG Mode) ==========
with tab3:
    st.markdown("*Ask questions about Meta Ads from Jim's course*")
    
    # Display RAG chat history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message["role"] == "assistant" and "citations" in message:
                citations = message["citations"]
                if citations.get("rule_ids") or citations.get("timestamps"):
                    st.markdown("---")
                    citation_text = " ".join([f"`[{r}]`" for r in citations.get("rule_ids", [])])
                    citation_text += " ".join([f"`[{t}]`" for t in citations.get("timestamps", [])])
                    st.markdown(f"📎 {citation_text}")
    
    # RAG chat input
    if prompt := st.chat_input("Ask about Meta Ads...", key="rag_input", disabled=not api_status):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        
        with st.chat_message("assistant"):
            with st.spinner("Searching..."):
                result = query_rag(prompt)
                
                if "error" in result:
                    response = f"⚠️ Error: {result['error']}"
                    citations = {}
                else:
                    response = result.get("answer", "No answer found.")
                    citations = result.get("citations", {})
                
                st.markdown(response)
                
                if citations.get("rule_ids") or citations.get("timestamps"):
                    st.markdown("---")
                    citation_text = " ".join([f"`[{r}]`" for r in citations.get("rule_ids", [])])
                    citation_text += " ".join([f"`[{t}]`" for t in citations.get("timestamps", [])])
                    st.markdown(f"📎 {citation_text}")
        
        st.session_state.messages.append({
            "role": "assistant",
            "content": response,
            "citations": citations
        })

# Welcome message for empty state
if not st.session_state.messages and not st.session_state.agent_messages and not st.session_state.generated_creative:
    st.info("""
    👋 **Welcome to MetaPilot!**
    
    Choose your mode:
    - **Campaign Builder**: Interactive assistant to gather requirements
    - **Creative Studio**: Generate headlines, descriptions, and body copy
    - **Knowledge Q&A**: Ask questions about Jim's methodology
    """)


