from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    database_url: str = "sqlite:///./warehouse-pro.db"
    jwt_secret: str = "development-only-secret"
    environment: str = "development"
    demo_mode: bool = True
    token_minutes: int = 120
    bootstrap_username: str = "admin"
    bootstrap_password: str = "0000"
    cors_origins: str = "http://localhost:5180,http://127.0.0.1:5180"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()

if settings.environment == "production":
    if len(settings.jwt_secret) < 32 or any(marker in settings.jwt_secret.upper() for marker in ('REPLACE', 'CHANGE_ME', 'DEVELOPMENT')):
        raise RuntimeError("Production requires a random JWT_SECRET of at least 32 characters")
    if settings.demo_mode or not settings.database_url.startswith('postgresql'):
        raise RuntimeError("Production requires DEMO_MODE=false and PostgreSQL")
    if len(settings.bootstrap_password) < 12 or any(marker in settings.bootstrap_password.upper() for marker in ('REPLACE', 'CHANGE_ME')):
        raise RuntimeError("Production requires a strong BOOTSTRAP_PASSWORD")
