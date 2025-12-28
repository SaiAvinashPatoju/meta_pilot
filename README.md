# MetaPilot Auto-Agent

RAG-based Meta Ads campaign assistant trained on Jim's Digital Marketing methodology.

## Architecture

```
[User] <--> [FastAPI] <--> [LangChain Agent]
                                  |
        +-------------------------+------------------------+
        |                         |                        |
  [Knowledge Base]         [Strategy Engine]       [Execution Engine]
  (Pinecone + Rules)       (Campaign Logic)        (Meta Graph API)
```

## Quick Start

### 1. Install Dependencies

```bash
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
copy .env.example .env
# Edit .env with your API keys:
# - OPENAI_API_KEY
# - PINECONE_API_KEY
# - PINECONE_ENVIRONMENT
# - PINECONE_INDEX_NAME
```

### 3. Run the Server

```bash
uvicorn app.main:app --reload
```

Server runs at: http://localhost:8000

## API Endpoints

### Ingest Video

```bash
curl -X POST http://localhost:8000/ingest \
  -H "Content-Type: application/json" \
  -d '{"youtube_id":"t0k4WndiQxk"}'
```

### Query Knowledge Base

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query":"What does Jim say about headline length?"}'
```

### List Playbook Rules

```bash
curl http://localhost:8000/rules
curl http://localhost:8000/rules?category=copywriting
```

### Validate Ad Copy

```bash
curl -X POST http://localhost:8000/validate \
  -H "Content-Type: application/json" \
  -d '{"text":"Shop Now","validation_type":"description"}'
```

## Testing

```bash
pytest tests/test_chunker.py -v
pytest tests/test_rules.py -v
```

## Project Structure

```
meta api/
├── app/
│   ├── main.py                 # FastAPI endpoints
│   ├── config.py               # Environment settings
│   ├── knowledge_base/
│   │   ├── transcriber.py      # YouTube → text
│   │   ├── chunker.py          # Text → chunks
│   │   ├── vector_store.py     # Pinecone integration
│   │   └── rules.py            # Playbook constraints
│   └── agent/
│       └── llm_client.py       # GPT-4o with grounding
├── tests/
├── data/transcripts/           # Cached transcripts
├── .env.example
├── requirements.txt
└── README.md
```

## Grounding & Anti-Hallucination

The LLM client enforces citation requirements:
- Answers must cite playbook rule IDs (e.g., `[COPY-001]`)
- Or reference video timestamps (e.g., `[07:58:00]`)
- Responses without citations are rejected with an abstain message

## License

Private - Jim's Digital Marketing methodology content.
