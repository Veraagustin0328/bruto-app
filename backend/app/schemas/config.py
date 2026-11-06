from datetime import time

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


class HorarioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    dia_semana: int  # 0 = lunes ... 6 = domingo
    abierto: bool
    abre: time
    cierra: time


class HorarioIn(BaseModel):
    dia_semana: int = Field(ge=0, le=6)
    abierto: bool = True
    abre: time
    cierra: time  # si es antes que "abre", cierra al día siguiente (pasada la medianoche)

    @model_validator(mode="after")
    def validar(self):
        if self.abre == self.cierra:
            raise ValueError(f"El {DIAS[self.dia_semana]} abre y cierra a la misma hora")
        return self


class HorariosIn(BaseModel):
    # Los 7 días de una, así no queda ninguno a medias
    dias: list[HorarioIn] = Field(min_length=7, max_length=7)

    @field_validator("dias")
    @classmethod
    def todos_los_dias(cls, v):
        if sorted(d.dia_semana for d in v) != list(range(7)):
            raise ValueError("Tienen que venir los 7 días, del 0 (lunes) al 6 (domingo), una vez cada uno")
        return v


class ConfigOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    link_pedidosya: str | None
    pedidos_pausados: bool
    mensaje_cerrado: str
    mensaje_pausado: str
    horarios: list[HorarioOut] = []


class ConfigCambios(BaseModel):
    link_pedidosya: str | None = Field(default=None, max_length=500)
    pedidos_pausados: bool | None = None
    mensaje_cerrado: str | None = Field(default=None, min_length=3, max_length=300)
    mensaje_pausado: str | None = Field(default=None, min_length=3, max_length=300)

    @field_validator("link_pedidosya")
    @classmethod
    def validar_link(cls, v):
        v = (v or "").strip()
        if v and not v.startswith("https://"):
            raise ValueError("El link tiene que empezar con https://")
        return v or None


class EstadoTienda(BaseModel):
    # Lo que usa el front para mostrar "Cantina abierta" o "Cerrado"
    abierto: bool  # dentro del horario
    pausado: bool  # Renzo pausó los pedidos
    acepta_pedidos: bool  # abierto y no pausado
    mensaje: str | None  # para mostrar si no acepta pedidos
    link_delivery: str | None  # PedidosYa, vacío hasta que Renzo lo pase
    horario_hoy: HorarioOut | None


class PausaIn(BaseModel):
    pausado: bool


class PausaOut(BaseModel):
    # Lo que ve la cantina en el interruptor de "Pausar pedidos"
    model_config = ConfigDict(from_attributes=True)

    pedidos_pausados: bool
    mensaje_pausado: str  # lo que ve el cliente mientras está pausado
