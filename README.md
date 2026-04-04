# MetaPilot

> **AI-powered Meta Ads campaign assistant** — Automates campaign creation, creative generation, and optimization using Retrieval-Augmented Generation (RAG) grounded in proven digital marketing methodology.

---

## Overview

MetaPilot is an end-to-end AI media buyer that guides users from a blank slate to a fully structured, ready-to-launch Meta (Facebook/Instagram) Ads campaign. It combines a conversational intake agent, a deterministic rules engine, an LLM-powered creative studio, and a Meta Marketing API execution layer — all grounded in Jim's *Learn Meta Ads Step-by-Step* course methodology.

**Target users:** Digital marketers, e-commerce business owners, and agencies managing Meta Ads campaigns — primarily targeting the Indian market (Tier-1 and Tier-2 cities).

**Core value proposition:**
- Eliminates guesswork by encoding expert ad-buying rules as hard constraints
- Prevents LLM hallucinations via mandatory citation grounding
- Reduces campaign setup time from hours to minutes
- Provides structured, reproducible campaign plans backed by playbook rules

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                         User Interfaces                          │
│           Streamlit Chat UI          FastAPI REST API            │
└──────────────────┬───────────────────────────┬───────────────────┘
                   │                           │
┌──────────────────▼───────────────────────────▼───────────────────┐
│                      FastAPI Application Layer                   │
│  /agent/*  /creative/*  /strategy/*  /ingest  /query  /meta/*   │
└──────┬─────────┬──────────────┬───────────────┬──────────────────┘
       │         │              │               │
┌──────▼──┐  ┌───▼────────┐  ┌─▼──────────┐  ┌▼───────────────┐
│  Agent  │  │  Creative  │  │  Strategy  │  │  Knowledge Base │
│  Layer  │  │   Studio   │  │   Engine   │  │  (RAG Pipeline) │
│         │  │            │  │            │  │                 │
│Conversa-│  │ Headline   │  │ Campaign   │  │ Transcriber     │
│tional   │  │ Desc.      │  │ Planner    │  │ Chunker         │
│Agent    │  │ Primary    │  │            │  │ Vector Store    │
│         │  │ Text Gen   │  │ Rules      │  │ (Pinecone)      │
└────┬────┘  └────────────┘  │ Engine     │  │                 │
     │                       └─────┬──────┘  │ Playbook Rules  │
┌────▼─────────────────────────────▼──────┐  └─────────────────┘
│            Engine / Infra Layer         │
│  ModelRouter  |  StateStore  |  Config  │
└─────────────────────────┬───────────────┘
                          │
              ┌───────────▼───────────┐
              │  Meta Marketing API   │
              │  (Auth + Executor)    │
              └───────────────────────┘
```

**Data Flow for a Campaign Build:**
1. User describes their product via the chat UI
2. Conversational agent gathers the **5 Pillars** (Objective, Budget, Targeting, USP, Creative)
3. Campaign Planner generates cold + warm ad set structure, enforcing playbook rules
4. Creative Studio generates headlines, descriptions, and primary text via Gemini LLM
5. All LLM outputs are validated against playbook rules and cited
6. Campaign plan is optionally executed via the Meta Marketing API

**RAG Query Flow:**
1. User asks a question → embedded via `text-embedding-004`
2. Pinecone semantic search retrieves top-k relevant transcript chunks
3. Gemini LLM generates a grounded answer, citing `[RULE-ID]` or `[timestamp]`
4. Answers without citations are rejected (anti-hallucination guard)

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Backend API** | Python 3.x, FastAPI, Uvicorn |
| **Frontend** | Streamlit |
| **LLM** | Google Gemini 2.0 Flash (`google-genai`) |
| **Embeddings** | Google `text-embedding-004` (768-dim vectors) |
| **Vector Database** | Pinecone (Serverless, AWS `us-east-1`) |
| **Text Splitting** | LangChain `langchain-text-splitters`, tiktoken |
| **YouTube Ingestion** | `youtube-transcript-api` |
| **Data Validation** | Pydantic v2, `pydantic-settings` |
| **Configuration** | `python-dotenv` |
| **Ad Platform API** | Meta Marketing API v18.0 (Graph API) |
| **Testing** | pytest, pytest-asyncio, httpx |
| **HTTP Client** | requests (Meta API calls) |

---

## Features

- **RAG Knowledge Base** — Ingests YouTube video transcripts, embeds them via Gemini, and stores in Pinecone for semantic retrieval with timestamp citations
- **Conversational Campaign Builder** — Guided 5-pillar intake agent collects Objective, Budget, Targeting, USP, and Creative details before generating a plan
- **Deterministic Rules Engine** — Hard-coded campaign optimization logic (learning phase protection, CPL threshold pausing, budget scaling cap at +20%) that the LLM explains but cannot override
- **Creative Studio** — Generates ad headlines (COPY-001), descriptions under 5 words (COPY-002), and PAS-framework primary text (COPY-004) with inline rule validation
- **Campaign Planner** — Automatically structures Cold (Prospecting) and Warm (Retargeting) ad sets with budget allocation (70/30 split) per CAMP-002
- **Playbook Rule System** — 12 hard-coded rules across Copywriting, Campaign Structure, Targeting, Pixel, and Budget categories; all LLM responses must cite at least one
- **Anti-Hallucination Grounding** — LLM responses without valid `[RULE-ID]` or `[timestamp]` citations are rejected and replaced with a safe abstain message
- **Model Router** — Routes tasks to appropriate Gemini configurations (temperature, token limits) based on task type (intake, copywriting, analysis, strategy)
- **Persistent State Store** — JSON-backed campaign state with decision logs, budget adjustment history, and creative performance tracking
- **Meta API Scaffold** — OAuth2 flow, token debug/refresh, campaign/ad-set/ad creation endpoints (requires valid credentials to execute)
- **Ad Copy Validation API** — Validates description length and USP keyword presence against playbook rules via REST endpoint

---

## Project Structure

```
meta_pilot/
├── app/
│   ├── main.py                      # FastAPI app — all route definitions
│   ├── config.py                    # Pydantic Settings — env var loading
│   │
│   ├── agent/                       # Primary conversational agent
│   │   ├── conversational.py        # MetaPilotAgent — session management & chat loop
│   │   ├── llm_client.py            # LLMClient — Gemini calls with grounding enforcement
│   │   ├── orchestrator.py          # Multi-agent orchestration (full workflow)
│   │   └── prompts.py               # System prompts, pillar guidance, summary templates
│   │
│   ├── agents/                      # Specialized sub-agents
│   │   ├── intake_agent.py          # Input validation, normalization, clarification
│   │   ├── analysis_agent.py        # Campaign performance analysis
│   │   ├── creative_agent.py        # Creative generation agent wrapper
│   │   └── strategy_agent.py        # Strategy recommendation agent
│   │
│   ├── creative/                    # Ad copy generators
│   │   ├── headline_gen.py          # Headline generation [COPY-001, COPY-003]
│   │   ├── description_gen.py       # Description generation [COPY-002]
│   │   └── primary_text_gen.py      # PAS-framework body copy [COPY-004]
│   │
│   ├── engine/                      # Core decision infrastructure
│   │   ├── rules_engine.py          # Deterministic rules (CPL, learning phase, scaling)
│   │   ├── model_router.py          # Task-based LLM model and parameter routing
│   │   └── state_store.py           # JSON-backed persistent campaign state
│   │
│   ├── knowledge_base/              # RAG pipeline
│   │   ├── transcriber.py           # YouTube transcript fetching with timestamps
│   │   ├── chunker.py               # LangChain text splitting with metadata preservation
│   │   ├── vector_store.py          # Pinecone upsert/query with Gemini embeddings
│   │   └── rules.py                 # Playbook rule definitions and validation functions
│   │
│   ├── meta/                        # Meta Marketing API integration (scaffold)
│   │   ├── auth.py                  # OAuth2 flow, token debug/exchange
│   │   ├── client.py                # Graph API client (campaign/adset/ad CRUD)
│   │   └── executor.py              # End-to-end campaign execution orchestrator
│   │
│   ├── models/
│   │   └── campaign.py              # Pydantic models: CampaignRequirements, ConversationState
│   │
│   └── strategy/
│       └── campaign_planner.py      # CampaignPlanner — ad set structure & budget logic
│
├── frontend/
│   └── app.py                       # Streamlit UI — Campaign Builder, Creative Studio, Q&A tabs
│
├── data/
│   ├── state/                       # JSON files for persisted campaign states
│   └── transcripts/                 # Cached transcript files
│
├── tests/
│   ├── test_rules.py                # Unit tests: playbook rules & validation functions
│   ├── test_creative.py             # Unit tests: headline/description/primary text models
│   └── test_chunker.py              # Unit tests: text chunking with timestamp metadata
│
├── .env.example                     # Environment variable template
├── requirements.txt                 # Python dependencies
└── README.md
```

---

## Getting Started

### Prerequisites

| Tool | Version |
|---|---|
| Python | 3.10+ |
| pip | Latest |
| Google Gemini API key | [Get one](https://aistudio.google.com/) |
| Pinecone account | [Sign up free](https://www.pinecone.io/) |
| Meta Developer App | Required only for campaign execution |

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/SaiAvinashPatoju/meta_pilot.git
cd meta_pilot

# 2. Create and activate virtual environment
python -m venv venv
source venv/bin/activate        # macOS/Linux
venv\Scripts\activate           # Windows

# 3. Install dependencies
pip install -r requirements.txt
```

### Environment Variables

Copy the example file and fill in your credentials:

```bash
cp .env.example .env
```

| Variable | Required | Description |
|---|---|---|
| `GEMINI_API_KEY` | ✅ Yes | Google AI Studio API key for LLM and embeddings |
| `PINECONE_API_KEY` | ✅ Yes | Pinecone API key for vector storage |
| `PINECONE_ENVIRONMENT` | ✅ Yes | Pinecone environment (default: `us-east-1`) |
| `PINECONE_INDEX_NAME` | ✅ Yes | Pinecone index name (default: `metapilot-kb`) |
| `META_APP_ID` | ⚠️ Campaign execution only | Meta Developer App ID |
| `META_APP_SECRET` | ⚠️ Campaign execution only | Meta Developer App Secret |
| `META_ACCESS_TOKEN` | ⚠️ Campaign execution only | Meta Ads Manager access token |
| `META_AD_ACCOUNT_ID` | ⚠️ Campaign execution only | Meta Ad Account ID (format: `act_XXXXXXXXX`) |
| `LLM_MODEL` | No | Override LLM model (default: `gemini-2.0-flash`) |
| `EMBEDDING_MODEL` | No | Override embedding model (default: `text-embedding-004`) |
| `STATE_STORAGE_DIR` | No | Directory for state persistence (default: `data/state`) |

**Optional rules engine thresholds** (configurable via env):

| Variable | Default | Description |
|---|---|---|
| `RULES_LEARNING_PHASE_DAYS` | `3` | Days before allowing structural changes |
| `RULES_MIN_LEADS` | `10` | Minimum leads required for decisions |
| `RULES_CPL_PAUSE_THRESHOLD` | `2.0` | Pause creative if CPL exceeds `N×` target |
| `RULES_CPL_SCALE_THRESHOLD` | `0.8` | Scale budget if CPL is below `N×` target |
| `RULES_MAX_BUDGET_INCREASE` | `0.20` | Maximum single budget increase (20%) |
| `RULES_MIN_SPEND_FOR_PAUSE` | `100` | Minimum USD spend before pausing creative |

### Running the Project

**Development (API only):**
```bash
uvicorn app.main:app --reload
# API available at http://localhost:8000
# Interactive docs at http://localhost:8000/docs
```

**Development (full stack):**
```bash
# Terminal 1 — API
uvicorn app.main:app --reload

# Terminal 2 — Frontend
streamlit run frontend/app.py
# UI available at http://localhost:8501
```

**Production:**
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

---

## API Documentation

All endpoints accept and return JSON. Interactive docs: `http://localhost:8000/docs`

### Health

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Health check — returns service name and version |

### Knowledge Base

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/ingest` | Ingest a YouTube video into Pinecone |
| `POST` | `/query` | Semantic search + grounded LLM answer |
| `GET` | `/rules` | List all playbook rules (optional `?category=`) |
| `POST` | `/validate` | Validate ad copy against playbook rules |
| `DELETE` | `/videos/{video_id}` | Remove all chunks for a video |

**Ingest a YouTube video:**
```bash
curl -X POST http://localhost:8000/ingest \
  -H "Content-Type: application/json" \
  -d '{"youtube_id": "t0k4WndiQxk", "chunk_size": 1000, "chunk_overlap": 200}'
```
```json
{
  "status": "ok",
  "video_id": "t0k4WndiQxk",
  "chunks_created": 84,
  "upsert_response": {"upserted": 84, "video_id": "t0k4WndiQxk"}
}
```

**Query the knowledge base:**
```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What does Jim say about headline length?", "top_k": 4}'
```
```json
{
  "answer": "Headlines must be concise and focused on the USP [COPY-001]. [07:58:00]",
  "grounded": true,
  "abstained": false,
  "citations": {"rule_ids": ["COPY-001"], "timestamps": ["07:58:00"]},
  "sources": [{"video_id": "t0k4WndiQxk", "timestamp_str": "07:58:00", "chunk_index": 12}]
}
```

**Validate ad copy:**
```bash
curl -X POST http://localhost:8000/validate \
  -H "Content-Type: application/json" \
  -d '{"text": "Shop Now", "validation_type": "description"}'
```
```json
{"valid": true, "word_count": 2, "rule_id": "COPY-002", "message": "Description has 2 words. Valid!"}
```

### Conversational Agent

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/agent/session` | Create a new campaign builder session |
| `POST` | `/agent/chat` | Send a message to the agent |
| `GET` | `/agent/session/{session_id}` | Get session state and 5-pillar progress |
| `GET` | `/agent/session/{session_id}/summary` | Get a formatted requirements summary |

**Start a session and chat:**
```bash
# Create session
SESSION=$(curl -s -X POST http://localhost:8000/agent/session | jq -r '.session_id')

# Chat
curl -X POST http://localhost:8000/agent/chat \
  -H "Content-Type: application/json" \
  -d "{\"session_id\": \"$SESSION\", \"message\": \"I want to run ads for my digital marketing course\"}"
```

### Strategy & Creative

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/strategy/plan` | Generate campaign plan from session requirements |
| `POST` | `/creative/headlines` | Generate headline variations |
| `POST` | `/creative/descriptions` | Generate descriptions (≤5 words, COPY-002) |
| `POST` | `/creative/primary-text` | Generate PAS-framework primary text |
| `POST` | `/creative/full-ad` | Generate complete ad creative (all formats) |

**Generate a full ad:**
```bash
curl -X POST http://localhost:8000/creative/full-ad \
  -H "Content-Type: application/json" \
  -d '{"product_name": "Digital Marketing Masterclass", "usp": "Learn Meta Ads in 30 days", "target_audience": "Small business owners in India"}'
```

### Meta API (requires credentials)

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/meta/auth/status` | Check Meta token validity and scopes |
| `GET` | `/meta/auth/url` | Get OAuth2 authorization URL |
| `POST` | `/meta/preview` | Preview campaign structure without executing |
| `POST` | `/meta/execute` | Execute campaign in Meta Ads Manager |

---

## Playbook Rules Reference

Rules are hard-coded constraints the LLM must cite. All 12 rules are available at `GET /rules`.

| Rule ID | Category | Rule Summary |
|---|---|---|
| `COPY-001` | copywriting | Headlines must be concise and focused on the USP |
| `COPY-002` | copywriting | Descriptions must be **under 5 words** |
| `COPY-003` | copywriting | Use different USPs for headline vs. description |
| `COPY-004` | copywriting | Primary text must follow **PAS** (Problem–Agitation–Solution) framework |
| `CAMP-001` | campaign_structure | Use Sales objective for e-commerce conversions |
| `CAMP-002` | campaign_structure | Create separate ad sets for Cold and Warm audiences |
| `CAMP-003` | campaign_structure | Use radius targeting for local businesses |
| `TARG-001` | targeting | Use precise interest targeting OR broad — not both |
| `TARG-002` | targeting | Retargeting must include video viewers, ATC, and page visitors |
| `PIXEL-001` | pixel | Facebook Pixel must be installed and verified before launch |
| `PIXEL-002` | pixel | Set up Conversion API (CAPI) for server-side tracking |
| `BUDGET-001` | budget | Start with $5–10/day per ad set for testing |
| `BUDGET-002` | budget | Use ABO for testing phase, CBO for scaling |

---

## Deployment

> ⚠️ Assumption: No CI/CD pipeline configuration was found in the repository. The steps below are recommended practices.

### Local / Single Server

```bash
# Install production dependencies
pip install -r requirements.txt

# Run with multiple workers
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Docker (Recommended)

> ⚠️ Assumption: A `Dockerfile` does not currently exist. The following is a recommended configuration.

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
```

### Environment Secrets

Never commit `.env` to version control. In production:
- Use your platform's secret manager (AWS Secrets Manager, GCP Secret Manager, etc.)
- Or inject environment variables directly into the container/process

### CORS Configuration

The FastAPI app currently allows all origins (`allow_origins=["*"]`). For production, restrict this to your frontend's domain in `app/main.py`.

---

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run specific test modules
pytest tests/test_rules.py -v
pytest tests/test_creative.py -v
pytest tests/test_chunker.py -v

# Run with coverage (requires pytest-cov)
pytest tests/ --cov=app --cov-report=term-missing
```

**Test coverage areas:**

| Module | Tests | What Is Covered |
|---|---|---|
| `test_rules.py` | 12 tests | Rule retrieval, uniqueness, category filtering, description/headline validation |
| `test_creative.py` | 6 tests | Creative result models, campaign planner (cold/warm ad sets), budget warnings |
| `test_chunker.py` | 8 tests | Text chunking, unique IDs, timestamp preservation, metadata correctness |

> ⚠️ Integration tests and end-to-end tests are not present. Tests that call external APIs (Gemini, Pinecone, Meta) require valid credentials and are not included.

---

## Observability

**Logging:** Standard Python `logging` module at `INFO` level. Key log events:

| Event | Log Level | Location |
|---|---|---|
| Ingestion start/end | `INFO` | `main.py` `/ingest` |
| Chunk creation count | `INFO` | `main.py` `/ingest` |
| Query processing | `INFO` | `main.py` `/query` |
| Ingestion/query errors | `ERROR` | `main.py` |

> ❗ Needs verification: No structured logging, metrics export (Prometheus/OpenTelemetry), or alerting is configured. These are recommended for production deployments.

---

## Security

| Concern | Implementation |
|---|---|
| **Secrets management** | API keys loaded from `.env` via `pydantic-settings`; `.env` is gitignored |
| **Meta authentication** | OAuth2 authorization code flow; short-lived tokens exchangeable for long-lived (60-day) tokens via `get_long_lived_token()` |
| **Token validation** | `debug_token()` calls Meta's `/debug_token` endpoint to verify token validity and scopes before any API calls |
| **CORS** | CORS middleware is enabled; currently allows all origins — restrict in production |
| **Input validation** | All request bodies validated via Pydantic models before processing |
| **No secrets in code** | All credentials loaded from environment variables — no hardcoded secrets |

**Required Meta OAuth2 scopes for campaign execution:**
- `ads_management`
- `ads_read`
- `business_management`
- `pages_read_engagement`

---

## Contributing

1. Fork the repository and create a feature branch: `git checkout -b feature/your-feature`
2. Make your changes and ensure existing tests pass: `pytest tests/ -v`
3. Add tests for new functionality in the `tests/` directory
4. Follow the existing code style — Pydantic models for data, singletons for services, docstrings on all classes and public methods
5. Open a pull request with a clear description of the change

**Adding a new playbook rule:** Edit `app/knowledge_base/rules.py` and add a `PlaybookRule` entry to `PLAYBOOK_RULES`. Assign the next sequential ID within its category (e.g., `COPY-005`).

**Adding a new API endpoint:** Add the route handler in `app/main.py` with a Pydantic request/response model. Follow the existing pattern of lazy-loading services via singleton getters.

---

## Roadmap

- [ ] **CI/CD pipeline** — GitHub Actions workflow for automated testing and linting on pull requests
- [ ] **Dockerfile + docker-compose** — Containerized deployment for API and frontend
- [ ] **Meta API full integration** — Complete and test the campaign execution scaffold with real credentials
- [ ] **Structured logging** — Replace `logging.basicConfig` with structured JSON logging for production observability
- [ ] **Authentication layer** — Add user authentication to the FastAPI app (JWT or OAuth2) before multi-tenant use
- [ ] **Async LLM calls** — Replace synchronous Gemini calls with `asyncio`-compatible async clients for better throughput
- [ ] **Expanded test coverage** — Integration tests for the RAG pipeline; mock-based tests for LLM/Pinecone clients
- [ ] **Webhook support** — Receive Meta campaign performance data via webhooks to feed the rules engine
- [ ] **Performance dashboard** — Streamlit tab or separate frontend for real-time campaign metrics and decision logs
- [ ] **Multi-language support** — Extend beyond English for Indian regional language ad copy generation

---

## License

> ⚠️ Assumption: No open-source license file is present. The original README noted: *"Private — Jim's Digital Marketing methodology content."*

This project is proprietary. The playbook rules and course content are derived from Jim's *Learn Meta Ads Step-by-Step* digital marketing course. All rights reserved.
