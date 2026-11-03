from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models import Rol


class UsuarioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    email: str
    rol: Rol
    activo: bool


class LoginOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    usuario: UsuarioOut


class UsuarioNuevo(BaseModel):
    nombre: str = Field(min_length=2, max_length=80)
    email: str = Field(min_length=5, max_length=120)
    password: str = Field(min_length=8, max_length=72)
    rol: Rol

    @field_validator("email")
    @classmethod
    def normalizar_email(cls, v: str):
        v = v.strip().lower()
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("el email no parece válido")
        return v


class UsuarioCambios(BaseModel):
    # Todo opcional: se cambia solo lo que venga
    nombre: str | None = Field(default=None, min_length=2, max_length=80)
    password: str | None = Field(default=None, min_length=8, max_length=72)
    rol: Rol | None = None
    activo: bool | None = None
