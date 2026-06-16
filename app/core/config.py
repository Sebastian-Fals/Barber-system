from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PROJECT_NAME: str = "Sistema Citas WhatsApp"
    API_V1_STR: str = "/api/v1"

    DATABASE_URL: str = "sqlite:///./citas.db"
    ADMIN_DATABASE_URL: Optional[str] = None
    ENCRYPTION_KEY: Optional[str] = None

    # WhatsApp — Evolution API
    EVOLUTION_API_URL: str

    # Calendar Webhook
    WEBHOOK_PUBLIC_URL: Optional[str] = None

    # Google
    GOOGLE_APPLICATION_CREDENTIALS: str = ""
    GOOGLE_APPLICATION_CREDENTIALS_JSON: Optional[str] = None
    GOOGLE_API_KEY: Optional[str] = None

    # App Settings
    TIMEZONE: str = "America/Bogota"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
