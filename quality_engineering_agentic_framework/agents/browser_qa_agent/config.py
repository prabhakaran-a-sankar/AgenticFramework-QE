from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # ── LLM Provider ──────────────────────────────────────────────────────────
    # Supported: anthropic | openai | azure_openai | gemini | ollama
    llm_provider: str = "anthropic"
    llm_model: str = "claude-sonnet-4-6"

    # Anthropic
    anthropic_api_key: str = ""

    # OpenAI / Azure OpenAI
    openai_api_key: str = ""
    azure_openai_endpoint: str = ""        # e.g. https://<resource>.openai.azure.com/
    azure_openai_api_version: str = ""     # e.g. 2024-02-15-preview

    # Google Gemini
    gemini_api_key: str = ""

    # Ollama (local)
    ollama_base_url: str = "http://localhost:11434"

    # Max agent steps per run
    max_agent_steps: int = 30

    # ── Database ──────────────────────────────────────────────────────────────
    database_url: str = "sqlite+aiosqlite:///./qa_agent.db"

    # ── Redis / Celery ────────────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"

    # ── Artifact storage ──────────────────────────────────────────────────────
    storage_backend: str = "local"         # local | s3
    storage_local_path: str = "./artifacts"
    s3_bucket: str = "qa-artifacts"
    s3_endpoint_url: str = ""             # blank=AWS; set for R2/MinIO/GCS
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_region: str = "us-east-1"

    # ── GitHub App ────────────────────────────────────────────────────────────
    github_app_id: str = ""
    github_private_key: str = ""
    github_webhook_secret: str = ""

    # ── Slack ─────────────────────────────────────────────────────────────────
    slack_webhook_url: str = ""

    # ── API ───────────────────────────────────────────────────────────────────
    api_host: str = "0.0.0.0"
    api_port: int = 8080
    secret_key: str = "change-me-in-production"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()
