from functools import lru_cache
import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[3]
load_dotenv(ROOT / ".env", override=False)


class Settings(BaseSettings):
    app_name: str = "EduAgent API"
    api_prefix: str = "/api"
    cors_origins: list[str] = ["http://localhost:3000"]
    llm_provider: str = "mock"
    users_dir: Path = ROOT / "data" / "users"
    courses_dir: Path = ROOT / "data" / "courses"
    kg_data_dir: Path = ROOT / "data" / "kg" / "data"
    cache_dir: Path = ROOT / "data" / "cache"
    resources_dir: Path = ROOT / "data" / "generated_resources"
    settings_dir: Path = ROOT / "data" / "settings"
    skills_dir: Path = ROOT / "skills"
    tools_dir: Path = ROOT / "tools"

    chroma_dir: Path = ROOT / "data" / "kg" / "chroma"
    chroma_collection: str = "edu_agent"
    embed_model_path: str = "BAAI/bge-small-zh-v1.5"
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_username: str = "neo4j"
    neo4j_password: str = ""

    model_config = SettingsConfigDict(
        env_file=str(ROOT / ".env"),
        env_prefix="EDU_AGENT_",
        extra="ignore",
    )

    @model_validator(mode="after")
    def merge_legacy_kg_env(self) -> "Settings":
        if not self.neo4j_password:
            self.neo4j_password = os.getenv("NEO4J_PASSWORD", "")
        if uri := os.getenv("NEO4J_URI"):
            self.neo4j_uri = uri
        if user := os.getenv("NEO4J_USERNAME"):
            self.neo4j_username = user
        if collection := os.getenv("CHROMA_COLLECTION"):
            self.chroma_collection = collection
        if model := os.getenv("LOCAL_EMBED_MODEL"):
            self.embed_model_path = model
        return self


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.resources_dir.mkdir(parents=True, exist_ok=True)
    settings.cache_dir.mkdir(parents=True, exist_ok=True)
    settings.courses_dir.mkdir(parents=True, exist_ok=True)
    settings.settings_dir.mkdir(parents=True, exist_ok=True)
    settings.kg_data_dir.mkdir(parents=True, exist_ok=True)
    settings.chroma_dir.mkdir(parents=True, exist_ok=True)
    return settings
