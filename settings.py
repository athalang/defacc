from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    model: str
    temperature: float
    max_tokens: int
    api_base: str

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

settings = Settings()
