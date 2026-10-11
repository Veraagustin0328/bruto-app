from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Lee todo del .env, si falta algo obligatorio explota al arrancar (mejor así)
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str

    jwt_secret: str
    jwt_expira_minutos: int = 720  # 12 hs, un turno largo de la cantina

    mp_access_token: str = ""
    mp_webhook_secret: str = ""

    frontend_url: str = "http://localhost:5173"
    backend_url: str = "http://localhost:8000"


settings = Settings()
