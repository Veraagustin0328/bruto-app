"""Las migraciones de Alembic corren de cero en una SQLite vacía y quedan igual que los modelos."""
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from app.config import settings

BACKEND = Path(__file__).resolve().parent.parent


def config_alembic(url: str) -> Config:
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "alembic"))
    return cfg


def test_migraciones_de_cero(tmp_path, monkeypatch):
    url = f"sqlite:///{(tmp_path / 'vacia.db').as_posix()}"
    # env.py toma la URL de settings
    monkeypatch.setattr(settings, "database_url", url)
    cfg = config_alembic(url)

    command.upgrade(cfg, "head")
    # Si los modelos tienen algo que no está en las migraciones, esto explota
    command.check(cfg)

    tablas = set(inspect(create_engine(url)).get_table_names())
    assert {"pedidos", "usuarios", "productos", "categorias"} <= tablas

    # Y se pueden deshacer hasta el principio
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
