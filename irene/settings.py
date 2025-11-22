from typing import Optional
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    model: str
    temperature: float
    api_base: Optional[str] = None
    api_key: Optional[str] = None

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

settings = Settings()
