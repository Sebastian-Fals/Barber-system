from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    PROJECT_NAME: str = "Sistema Citas WhatsApp"
    API_V1_STR: str = "/api/v1"
    
    DATABASE_URL: str = "sqlite:///./citas.db"
    
    # WhatsApp
    WHATSAPP_API_TOKEN: str
    WHATSAPP_VERIFY_TOKEN: str
    
    # Google
    GOOGLE_APPLICATION_CREDENTIALS: str
    GOOGLE_API_KEY: Optional[str] = None
    
    # App Settings
    TIMEZONE: str = "America/Bogota"

    class Config:
        env_file = ".env"

settings = Settings()
