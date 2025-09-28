from typing import List
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    # Application
    APP_NAME: str = Field(default="Podcast Summarizer API")
    APP_VERSION: str = Field(default="1.0.0")
    DEBUG: bool = Field(default=False)

    # Database
    DATABASE_URL: str = Field(default="postgresql+asyncpg://podcast_user:podcast_pass@localhost:5432/podcast_db")

    # Security
    SECRET_KEY: str = Field(default="your-secret-key-here-change-in-production")
    ALGORITHM: str = Field(default="HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30)

    # AWS Configuration
    AWS_REGION: str = Field(default="us-east-1")
    AWS_ACCESS_KEY_ID: str | None = Field(default=None)
    AWS_SECRET_ACCESS_KEY: str | None = Field(default=None)
    S3_BUCKET_NAME: str = Field(default="podcast-audio-bucket")

    # Amazon Bedrock
    BEDROCK_MODEL_ID: str = Field(default="anthropic.claude-3-sonnet-20240229-v1:0")

    # Google Gemini (Fallback)
    GEMINI_API_KEY: str | None = Field(default=None)
    GEMINI_MODEL_NAME: str = Field(default="gemini-1.5-flash")

    # API Settings
    API_V1_PREFIX: str = Field(default="/api/v1")
    CORS_ORIGINS: List[str] = Field(default=["http://localhost:3000", "http://localhost:8000"])

    # Podcast Ingestion Settings
    MAX_EPISODES_PER_PODCAST: int = Field(default=3)
    TRANSCRIPTION_TIMEOUT_SECONDS: int = Field(default=300)

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()