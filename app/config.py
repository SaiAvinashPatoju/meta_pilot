import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    # Google Gemini (for LLM and embeddings)
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    
    # Pinecone
    pinecone_api_key: str = os.getenv("PINECONE_API_KEY", "")
    pinecone_environment: str = os.getenv("PINECONE_ENVIRONMENT", "us-east-1")
    pinecone_index_name: str = os.getenv("PINECONE_INDEX_NAME", "metapilot-kb")
    
    # LLM settings - Multi-model configuration
    llm_model: str = os.getenv("LLM_MODEL", "gemini-2.0-flash")
    llm_model_pro: str = os.getenv("LLM_MODEL_PRO", "gemini-2.0-flash")  # For quality tasks
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "text-embedding-004")
    
    # State store settings
    state_storage_dir: str = os.getenv("STATE_STORAGE_DIR", "data/state")
    
    # Rules engine thresholds (can be overridden via env)
    rules_learning_phase_days: int = int(os.getenv("RULES_LEARNING_PHASE_DAYS", "3"))
    rules_min_leads_for_decision: int = int(os.getenv("RULES_MIN_LEADS", "10"))
    rules_cpl_pause_threshold: float = float(os.getenv("RULES_CPL_PAUSE_THRESHOLD", "2.0"))
    rules_cpl_scale_threshold: float = float(os.getenv("RULES_CPL_SCALE_THRESHOLD", "0.8"))
    rules_max_budget_increase: float = float(os.getenv("RULES_MAX_BUDGET_INCREASE", "0.20"))
    rules_min_spend_for_pause: float = float(os.getenv("RULES_MIN_SPEND_FOR_PAUSE", "100"))
    
    # Default targeting for Indian market
    default_locations: list = ["India"]
    default_age_min: int = 22
    default_age_max: int = 38
    
    class Config:
        env_file = ".env"


settings = Settings()
