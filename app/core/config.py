from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PROJECT_NAME: str = "Sistema Citas WhatsApp"
    API_V1_STR: str = "/api/v1"

    DATABASE_URL: str = "sqlite:///./citas.db"
    ADMIN_DATABASE_URL: Optional[str] = None
    ENCRYPTION_KEY: Optional[str] = None

    # WhatsApp
    WHATSAPP_API_TOKEN: str
    WHATSAPP_VERIFY_TOKEN: str

    # Calendar Webhook
    WEBHOOK_PUBLIC_URL: Optional[str] = None

    # Google
    GOOGLE_APPLICATION_CREDENTIALS: str = ""
    GOOGLE_APPLICATION_CREDENTIALS_JSON: Optional[str] = None
    GOOGLE_API_KEY: Optional[str] = None

    # App Settings
    TIMEZONE: str = "America/Bogota"

    class Config:
        env_file = ".env"


settings = Settings()
