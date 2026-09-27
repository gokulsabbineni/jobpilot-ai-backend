from functools import lru_cache
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):\n    agent_poll_interval_seconds: int = 600
    app_name: str = "JobPilot AI"
    environment: str = "development"
    debug: bool = False
    secret_key: str = "change-me"
    access_token_expire_minutes: int = 1440
    database_url: str = "sqlite:///./jobpilot.db"
    redis_url: str = "redis://localhost:6379/0"
    llm_provider: str = "ollama"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"
    openai_api_key: str | None = None
    openai_model: str = "gpt-5-mini"
    storage_dir: str = "./storage/resumes"
    cors_origins: str = "http://localhost:5173,https://jobpilot-ai-eta.vercel.app"

    # Optional persistent object storage for free cloud deployments.
    supabase_url: str | None = None
    supabase_service_role_key: str | None = None
    supabase_storage_bucket: str = "resumes"

    # Optional production admin bootstrap credentials.
    admin_email: str | None = None
    admin_password: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [x.strip() for x in self.cors_origins.split(",") if x.strip()]

    @property
    def uses_supabase_storage(self) -> bool:
        return bool(self.supabase_url and self.supabase_service_role_key)

    @model_validator(mode="after")
    def validate_production(self):
        if self.environment.lower() in {"production", "prod"}:
            if self.secret_key == "change-me" or len(self.secret_key) < 32:
                raise ValueError(
                    "SECRET_KEY must be a strong 32+ character value in production"
                )
            if self.debug:
                raise ValueError("DEBUG must be false in production")
            if self.database_url.startswith("sqlite"):
                raise ValueError("DATABASE_URL must use PostgreSQL in production")
            if not self.uses_supabase_storage:
                raise ValueError(
                    "Supabase Storage must be configured in production "
                    "so uploaded resumes survive free-host restarts"
                )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
