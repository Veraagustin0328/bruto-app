from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

# pool_pre_ping para que no se caiga si Postgres corta conexiones viejas
engine = create_engine(settings.database_url, pool_pre_ping=True)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    # Dependencia de FastAPI: abre una sesión por request y la cierra al final
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
