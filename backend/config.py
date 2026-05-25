from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    anthropic_api_key: str = ""
    claude_model: str = "claude-sonnet-4-6"
    # On Railway, set CHROMA_PERSIST_DIR=/data/chroma_db and mount a volume at /data
    chroma_persist_dir: str = "./chroma_db"
    embedding_model: str = "all-MiniLM-L6-v2"
    max_tokens: int = 2048
    top_k: int = 10
    port: int = 8000

    class Config:
        env_file = ".env"


settings = Settings()
