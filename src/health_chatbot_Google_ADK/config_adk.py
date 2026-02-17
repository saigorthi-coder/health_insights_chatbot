"""Configuration for Google ADK migration.

Authentication:
- Gemini API: Default service account via ADC (Application Default Credentials).
  No API key needed. Set via: gcloud auth application-default login
- BigQuery: Personal account via gcloud auth login.
- LangFuse: Keys provided via environment variables.
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


# ============================================================
# BigQuery Constants (unchanged from config.py)
# ============================================================

BQ_PROJECT = "project-ad8e168b-9904-43b7-b43"
BQ_DATASET = "Vector_AI_POC"
BQ_TABLE = "Health_Insurance_Synthetic_PT_ID"

FULL_TABLE_NAME = f"`{BQ_PROJECT}.{BQ_DATASET}.{BQ_TABLE}`"

DB_MAX_SQL_RETRIES = 3


# ============================================================
# ADK Configuration
# ============================================================

class ADKConfigs(BaseSettings):
    """Configuration settings for Google ADK migration.

    Loads from environment variables / .env file.
    """

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", env_ignore_empty=True
    )

    # Model selection
    default_planner_model: str = "gemini-2.5-flash"
    default_worker_model: str = "gemini-2.5-flash"

    # Use Vertex AI (ADC-based auth, no API key needed)
    # Set to TRUE to use default service account credentials
    google_genai_use_vertexai: str = "TRUE"
    google_cloud_project: str = BQ_PROJECT
    google_cloud_location: str = "us-central1"

    # Gemini grounding web search (optional - keep existing proxy)
    web_search_base_url: str | None = None
    web_search_api_key: str | None = None

    # LangFuse (observability)
    langfuse_public_key: str | None = Field(default=None)
    langfuse_secret_key: str | None = Field(default=None)
    langfuse_host: str = "https://us.cloud.langfuse.com"
