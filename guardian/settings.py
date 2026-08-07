from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    model: str
    temperature: float
    api_base: Optional[str] = None
    api_key: Optional[str] = None

settings = Settings()
