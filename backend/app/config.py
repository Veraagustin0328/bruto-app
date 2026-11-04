from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/.env, se corra desde donde se corra (uvicorn, alembic, scripts)
ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    # Lee todo del .env, si falta algo obligatorio explota al arrancar (mejor así)
    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore")

    database_url: str

    jwt_secret: str
    jwt_expira_minutos: int = 720  # 12 hs, un turno largo de la cantina

    mp_access_token: str = ""
    mp_webhook_secret: str = ""

    # Minutos que tiene el cliente para pagar con MP. A esa altura vence el link
    # y la tarea de fondo cancela el pedido si nadie lo pagó
    minutos_para_pagar: int = 30

    frontend_url: str = "http://localhost:5173"
    backend_url: str = "http://localhost:8001"

    zona_horaria: str = "America/Argentina/Mendoza"

    # La numeración de pedidos (#001, #002...) arranca de nuevo a esta hora.
    # No es a las 00:00 porque la cantina cierra pasada la medianoche y
    # no queremos que vuelva al #001 en medio del turno
    hora_corte_jornada: int = 6


settings = Settings()
