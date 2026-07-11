"""
Configuration management for FastAPI backend
"""
import os
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings from environment variables"""
    
    # PostgreSQL
    database_host: str = "localhost"
    database_port: int = 5432
    database_user: str = "postgres"
    database_password: str = ""
    database_name: str = "postgres"
    database_ssl: bool = False
    
    # OpenAI
    openai_api_key: str = ""
    openai_model: str = "gpt-4-turbo"
    # Azure OpenAI (deployment-based)
    azure_openai_api_key: str = ""
    azure_openai_endpoint: str = ""
    azure_openai_deployment: str = ""
    azure_openai_api_version: str = "2024-12-01-preview"
    # Groq API (set via environment variable at runtime; do NOT commit secrets)
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    
    # FastAPI
    fastapi_host: str = "0.0.0.0"
    fastapi_port: int = 8000
    fastapi_reload: bool = False
    
    # CORS
    cors_origins: str = "http://localhost:3000,http://localhost:5173"
    
    # Logging
    log_level: str = "INFO"
    
    # MCP server
    mcp_server_url: str = "http://127.0.0.1:8001"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
    
    @property
    def cors_origins_list(self):
        """Convert comma-separated origins to list"""
        return [origin.strip() for origin in self.cors_origins.split(",")]


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()
