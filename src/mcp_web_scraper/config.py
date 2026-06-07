from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    mcp_host: str = Field(default="0.0.0.0", alias="MCP_HOST")
    mcp_port: int = Field(default=8000, alias="MCP_PORT")
    ollama_host: str = Field(
        default="http://host.docker.internal:11434",
        alias="OLLAMA_HOST",
    )
    ollama_model: str = Field(default="deepseek-r1:7b", alias="OLLAMA_MODEL")
    scrape_timeout_s: float = Field(default=30.0, alias="SCRAPE_TIMEOUT_S")
    scrape_max_bytes: int = Field(default=2_097_152, alias="SCRAPE_MAX_BYTES")
    mcp_api_key: str = Field(default="", alias="MCP_API_KEY")
    allowed_origins: str = Field(default="*", alias="ALLOWED_ORIGINS")
    user_agent: str = Field(default="mcp-web-scraper/0.1.0", alias="USER_AGENT")


def get_settings() -> Settings:
    return Settings()
