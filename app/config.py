from pydantic_settings import BaseSettings
from pydantic import ConfigDict
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env")
    # Google Gemini (for LLM and embeddings)
    gemini_api_key: str = ""

    # Pinecone
    pinecone_api_key: str = ""
    pinecone_environment: str = "us-east-1"
    pinecone_index_name: str = "metapilot-kb"

    # LLM settings - Multi-model configuration
    llm_model: str = "gemini-2.0-flash"
    llm_model_pro: str = "gemini-2.0-flash"  # For quality tasks
    embedding_model: str = "text-embedding-004"

    # State store settings
    state_storage_dir: str = "data/state"

    # Rules engine thresholds (can be overridden via env)
    rules_learning_phase_days: int = 3
    rules_min_leads_for_decision: int = 10
    rules_cpl_pause_threshold: float = 2.0
    rules_cpl_scale_threshold: float = 0.8
    rules_max_budget_increase: float = 0.20
    rules_min_spend_for_pause: float = 100.0

    # Default targeting for Indian market
    default_locations: list = ["India"]
    default_age_min: int = 22
    default_age_max: int = 38

    # Meta Marketing API
    meta_app_id: str = ""
    meta_app_secret: str = ""
    meta_access_token: str = ""
    meta_ad_account_id: str = ""
    meta_redirect_uri: str = "http://localhost:8000/auth/callback"


settings = Settings()
