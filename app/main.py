"""
MetaPilot Auto-Agent FastAPI Application.
RAG-based API for ingesting YouTube content and answering questions with grounded citations.
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import logging

from app.knowledge_base.transcriber import transcribe_youtube, get_transcript_with_timestamps
from app.knowledge_base.chunker import chunk_text, chunk_with_timestamps
from app.knowledge_base.vector_store import VectorStore
from app.knowledge_base.rules import get_all_rules, get_rules_by_category, validate_description_length
from app.agent.llm_client import answer_with_context

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="MetaPilot Auto-Agent API",
    description="RAG-based Meta Ads campaign assistant trained on Jim's Digital Marketing methodology",
    version="0.1.0"
)

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize vector store (lazy loading)
_vector_store: Optional[VectorStore] = None


def get_vector_store() -> VectorStore:
    """Get or create vector store singleton."""
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store


# ============ Request/Response Models ============

class IngestRequest(BaseModel):
    youtube_id: str
    chunk_size: int = 1000
    chunk_overlap: int = 200


class IngestResponse(BaseModel):
    status: str
    video_id: str
    chunks_created: int
    upsert_response: dict


class QueryRequest(BaseModel):
    query: str
    top_k: int = 4
    video_id: Optional[str] = None  # Optional filter by video


class QueryResponse(BaseModel):
    answer: str
    grounded: bool
    abstained: bool
    citations: dict
    sources: List[dict]


class ValidationRequest(BaseModel):
    text: str
    validation_type: str  # "description" or "headline"
    usp_keywords: Optional[List[str]] = None


# ============ API Endpoints ============

@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "MetaPilot Auto-Agent",
        "version": "0.1.0"
    }


@app.get("/rules")
async def list_rules(category: Optional[str] = None):
    """List all playbook rules, optionally filtered by category."""
    if category:
        rules = get_rules_by_category(category)
    else:
        rules = get_all_rules()
    
    return {
        "count": len(rules),
        "rules": [r.model_dump() for r in rules]
    }


@app.post("/ingest", response_model=IngestResponse)
async def ingest(req: IngestRequest):
    """
    Ingest a YouTube video into the knowledge base.
    
    Flow: YouTube URL → transcript → chunks → embeddings → Pinecone
    """
    try:
        logger.info(f"Starting ingestion for video: {req.youtube_id}")
        
        # Step 1: Fetch transcript with timestamps
        segments = get_transcript_with_timestamps(req.youtube_id)
        logger.info(f"Fetched {len(segments)} transcript segments")
        
        # Step 2: Chunk with timestamp preservation
        chunks = chunk_with_timestamps(
            segments=segments,
            chunk_size=req.chunk_size,
            chunk_overlap=req.chunk_overlap,
            video_id=req.youtube_id
        )
        logger.info(f"Created {len(chunks)} chunks")
        
        # Step 3: Upsert to vector store
        vs = get_vector_store()
        upsert_result = vs.upsert_chunks(req.youtube_id, chunks)
        logger.info(f"Upserted {upsert_result['upserted']} vectors")
        
        return IngestResponse(
            status="ok",
            video_id=req.youtube_id,
            chunks_created=len(chunks),
            upsert_response=upsert_result
        )
        
    except Exception as e:
        logger.error(f"Ingestion failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/query", response_model=QueryResponse)
async def query(req: QueryRequest):
    """
    Query the knowledge base and get a grounded answer.
    
    Flow: question → vector search → LLM with context → grounded answer with citations
    """
    try:
        logger.info(f"Processing query: {req.query[:100]}...")
        
        # Step 1: Retrieve relevant chunks
        vs = get_vector_store()
        filter_dict = {"video_id": req.video_id} if req.video_id else None
        results = vs.query(req.query, top_k=req.top_k, filter=filter_dict)
        
        if not results:
            return QueryResponse(
                answer="I couldn't find any relevant information in the course materials for this question.",
                grounded=False,
                abstained=True,
                citations={},
                sources=[]
            )
        
        logger.info(f"Retrieved {len(results)} chunks")
        
        # Step 2: Build context from retrieved chunks
        context_snippets = "\n\n".join([
            f"[{r['metadata'].get('timestamp_str', 'n/a')}] {r['text']}"
            for r in results
        ])
        
        # Step 3: Get LLM answer with grounding
        llm_response = answer_with_context(
            req.query,
            context_snippets,
            [r['metadata'] for r in results]
        )
        
        return QueryResponse(
            answer=llm_response["answer"],
            grounded=llm_response["grounded"],
            abstained=llm_response.get("abstained", False),
            citations=llm_response["citations"],
            sources=[r['metadata'] for r in results]
        )
        
    except Exception as e:
        logger.error(f"Query failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/validate")
async def validate_copy(req: ValidationRequest):
    """
    Validate ad copy against playbook rules.
    """
    if req.validation_type == "description":
        result = validate_description_length(req.text)
    elif req.validation_type == "headline":
        from app.knowledge_base.rules import validate_headline_has_usp
        keywords = req.usp_keywords or []
        result = validate_headline_has_usp(req.text, keywords)
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown validation type: {req.validation_type}"
        )
    
    return result


@app.delete("/videos/{video_id}")
async def delete_video(video_id: str):
    """Delete all chunks for a specific video from the knowledge base."""
    try:
        vs = get_vector_store()
        result = vs.delete_by_video(video_id)
        return result
    except Exception as e:
        logger.error(f"Delete failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ Conversational Agent Endpoints ============

class ChatRequest(BaseModel):
    session_id: str
    message: str


class SessionResponse(BaseModel):
    session_id: str
    welcome_message: str


@app.post("/agent/session", response_model=SessionResponse)
async def create_session():
    """Create a new conversation session with the agent."""
    from app.agent.conversational import get_agent
    
    agent = get_agent()
    session_id = agent.create_session()
    welcome = agent.get_welcome_message(session_id)
    
    return SessionResponse(
        session_id=session_id,
        welcome_message=welcome
    )


@app.post("/agent/chat")
async def agent_chat(req: ChatRequest):
    """Chat with the conversational agent."""
    from app.agent.conversational import get_agent
    
    agent = get_agent()
    result = agent.chat(req.session_id, req.message)
    
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    
    return result


@app.get("/agent/session/{session_id}")
async def get_session_state(session_id: str):
    """Get the current state of a session."""
    from app.agent.conversational import get_agent
    
    agent = get_agent()
    state = agent.get_session(session_id)
    
    if not state:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return {
        "session_id": session_id,
        "requirements": state.requirements.model_dump(),
        "phase": state.phase,
        "complete": state.requirements.is_complete(),
        "progress": state.requirements.completion_percentage(),
        "missing_pillars": state.requirements.missing_pillars()
    }


@app.get("/agent/session/{session_id}/summary")
async def get_session_summary(session_id: str):
    """Get a summary of the collected requirements."""
    from app.agent.conversational import get_agent
    
    agent = get_agent()
    summary = agent.generate_summary(session_id)
    
    return {"summary": summary}


# ============ Strategy & Creative Endpoints ============

class GeneratePlanRequest(BaseModel):
    session_id: str


class GenerateCreativeRequest(BaseModel):
    product_name: str
    usp: str
    target_audience: Optional[str] = None
    usp_keywords: Optional[List[str]] = None


@app.post("/strategy/plan")
async def generate_campaign_plan(req: GeneratePlanRequest):
    """Generate a campaign plan from session requirements."""
    from app.agent.conversational import get_agent
    from app.strategy.campaign_planner import get_campaign_planner
    
    agent = get_agent()
    state = agent.get_session(req.session_id)
    
    if not state:
        raise HTTPException(status_code=404, detail="Session not found")
    
    if not state.requirements.is_complete():
        raise HTTPException(
            status_code=400, 
            detail=f"Requirements incomplete. Missing: {state.requirements.missing_pillars()}"
        )
    
    planner = get_campaign_planner()
    plan = planner.generate_plan(state.requirements)
    
    return plan.model_dump()


@app.post("/creative/headlines")
async def generate_headlines(req: GenerateCreativeRequest):
    """Generate headline variations."""
    from app.creative.headline_gen import get_headline_generator
    
    generator = get_headline_generator()
    result = generator.generate(
        product_name=req.product_name,
        usp=req.usp,
        usp_keywords=req.usp_keywords,
        target_audience=req.target_audience
    )
    
    return result.model_dump()


@app.post("/creative/descriptions")
async def generate_descriptions(req: GenerateCreativeRequest):
    """Generate description variations (under 5 words per COPY-002)."""
    from app.creative.description_gen import get_description_generator
    
    generator = get_description_generator()
    result = generator.generate(
        product_name=req.product_name,
        usp=req.usp
    )
    
    return result.model_dump()


@app.post("/creative/primary-text")
async def generate_primary_text(req: GenerateCreativeRequest):
    """Generate primary text using PAS framework."""
    from app.creative.primary_text_gen import get_primary_text_generator
    
    generator = get_primary_text_generator()
    result = generator.generate(
        product_name=req.product_name,
        usp=req.usp,
        target_audience=req.target_audience
    )
    
    return result.model_dump()


@app.post("/creative/full-ad")
async def generate_full_ad(req: GenerateCreativeRequest):
    """Generate complete ad creative (headlines + descriptions + primary text)."""
    from app.creative.headline_gen import get_headline_generator
    from app.creative.description_gen import get_description_generator
    from app.creative.primary_text_gen import get_primary_text_generator
    
    headlines = get_headline_generator().generate(
        product_name=req.product_name,
        usp=req.usp,
        usp_keywords=req.usp_keywords,
        target_audience=req.target_audience,
        count=3
    )
    
    descriptions = get_description_generator().generate(
        product_name=req.product_name,
        usp=req.usp,
        count=3
    )
    
    primary_text = get_primary_text_generator().generate(
        product_name=req.product_name,
        usp=req.usp,
        target_audience=req.target_audience,
        count=2
    )
    
    return {
        "headlines": headlines.model_dump(),
        "descriptions": descriptions.model_dump(),
        "primary_text": primary_text.model_dump(),
        "rule_citations": ["COPY-001", "COPY-002", "COPY-003", "COPY-004"]
    }
