"""
Configuration module for Medical Report Analyzer.
Loads environment variables and provides app-wide settings.
"""

import os
import secrets
from pathlib import Path
from functools import lru_cache

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # --- App ---
    APP_NAME: str = "Medical Report Analyzer"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # --- Database ---
    DATABASE_URL: str = "sqlite:///./medical_analyzer.db"

    # --- Encryption ---
    ENCRYPTION_KEY: str = Field(
        default_factory=lambda: os.getenv(
            "ENCRYPTION_KEY",
            secrets.token_urlsafe(32),
        )
    )

    # --- Claude API ---
    ANTHROPIC_API_KEY: str = ""
    CLAUDE_MODEL: str = "claude-opus-4-5"
    CLAUDE_MAX_TOKENS: int = 4096

    # --- HuggingFace NER ---
    NER_MODEL_NAME: str = "d4data/biomedical-ner-all"
    NER_CACHE_DIR: str = "./model_cache"

    # --- OCR ---
    OCR_ENGINE: str = "surya"  # "surya" | "paddle" | "pdfplumber"

    # --- Uploads ---
    UPLOAD_DIR: str = "./uploads"
    MAX_FILE_SIZE_MB: int = 50
    ALLOWED_EXTENSIONS: list[str] = [".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".bmp"]

    # --- OpenFDA ---
    OPENFDA_BASE_URL: str = "https://api.fda.gov/drug/label.json"

    # --- Paths ---
    BASE_DIR: Path = Path(__file__).resolve().parent

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Ensure required directories exist
settings = get_settings()
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
os.makedirs(settings.NER_CACHE_DIR, exist_ok=True)
