from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Agente AI Pro"
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/agente_ai_pro"

    jwt_secret_key: str = "change_me"
    jwt_refresh_secret_key: str = "change_me_refresh"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_minutes: int = 60 * 24 * 7

    smtp_enabled: bool = False
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""

    request_timeout_seconds: int = 12
    request_retries: int = 3
    rate_limit_per_minute: int = 80


settings = Settings()
