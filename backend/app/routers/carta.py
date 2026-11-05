"""
La carta desde el panel. Todo solo admin (Renzo), salvo prender/apagar
un producto o una opción, que también lo hace la cantina (la bondiola sin stock).

Cada cambio le manda "carta_actualizada" al WebSocket del panel.
"""
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import requiere_rol
from app.models import Categoria, GrupoOpciones, Opcion, Producto, Rol, Usuario
from app.schemas.carta import (
    AumentoPrecios,
    CategoriaAdmin,
    CategoriaCambios,
    CategoriaNueva,
    Disponibilidad,
    GrupoAdmin,
    GrupoCambios,
    GrupoNuevo,
    NuevoOrden,
    OpcionAdmin,
    OpcionCambios,
    OpcionNueva,
    ProductoAdmin,
    ProductoCambios,
    ProductoNuevo,
    VistaPreviaAumento,
)
from app.services import carta as srv
from app.ws import avisar_carta

solo_admin = requiere_rol(Rol.admin)
admin_o_cantina = requiere_rol(Rol.cantina)

router = APIRouter(prefix="/api/carta", tags=["Carta y precios"])


def error(e: srv.CartaInvalida):
    codigo = status.HTTP_404_NOT_FOUND if isinstance(e, srv.NoExiste) else status.HTTP_400_BAD_REQUEST
    return HTTPException(status_code=codigo, detail=str(e))


def traer(db, modelo, id_, nombre):
    try:
        return srv.traer(db, modelo, id_, nombre)
    except srv.CartaInvalida as e:
        raise error(e)


def guardar(db: Session, avisos: BackgroundTasks, obj=None):
    db.commit()
    if obj is not None:
        db.refresh(obj)
    avisos.add_task(avisar_carta)
    return obj


# ---------- ver todo ----------


@router.get("", response_model=list[CategoriaAdmin])
def ver_carta(db: Session = Depends(get_db), _: Usuario = Depends(admin_o_cantina)):
    # Todo, incluidas categorías inactivas, productos no visibles y opciones apagadas.
    # La cantina también la puede ver: la necesita para prender y apagar
    return srv.carta_completa(db)


# ---------- categorías ----------


@router.post("/categorias", response_model=CategoriaAdmin, status_code=201)
def crear_categoria(
    datos: CategoriaNueva, avisos: BackgroundTasks,
    db: Session = Depends(get_db), _: Usuario = Depends(solo_admin),
):
    cat = Categoria(
        nombre=datos.nombre.strip(), activa=datos.activa,
        orden=srv.siguiente_orden(db, Categoria.orden),
    )
    db.add(cat)
    return guardar(db, avisos, cat)


@router.patch("/categorias/{categoria_id}", response_model=CategoriaAdmin)
def editar_categoria(
    categoria_id: int, cambios: CategoriaCambios, avisos: BackgroundTasks,
    db: Session = Depends(get_db), _: Usuario = Depends(solo_admin),
):
    cat = traer(db, Categoria, categoria_id, "categoría")
    srv.aplicar_cambios(cat, cambios)
    return guardar(db, avisos, cat)


@router.delete("/categorias/{categoria_id}", status_code=204)
def borrar_categoria(
    categoria_id: int, avisos: BackgroundTasks,
    db: Session = Depends(get_db), _: Usuario = Depends(solo_admin),
):
    cat = traer(db, Categoria, categoria_id, "categoría")
    if cat.productos:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La categoría tiene productos. Movelos o borralos antes, o desactivala",
        )
    db.delete(cat)
    guardar(db, avisos)
    return Response(status_code=204)


@router.put("/categorias/orden", response_model=list[CategoriaAdmin])
def ordenar_categorias(
    orden: NuevoOrden, avisos: BackgroundTasks,
    db: Session = Depends(get_db), _: Usuario = Depends(solo_admin),
):
    try:
        srv.reordenar(list(db.scalars(select(Categoria))), orden.ids)
    except srv.CartaInvalida as e:
        raise error(e)
    guardar(db, avisos)
    return srv.carta_completa(db)


@router.put("/categorias/{categoria_id}/orden-productos", response_model=CategoriaAdmin)
def ordenar_productos(
    categoria_id: int, orden: NuevoOrden, avisos: BackgroundTasks,
    db: Session = Depends(get_db), _: Usuario = Depends(solo_admin),
):
    cat = traer(db, Categoria, categoria_id, "categoría")
    try:
        srv.reordenar(cat.productos, orden.ids)
    except srv.CartaInvalida as e:
        raise error(e)
    db.commit()
    db.expire(cat, ["productos"])  # que vuelva a leerlos en el orden nuevo
    avisos.add_task(avisar_carta)
    return cat


# ---------- productos ----------


@router.post("/productos", response_model=ProductoAdmin, status_code=201)
def crear_producto(
    datos: ProductoNuevo, avisos: BackgroundTasks,
    db: Session = Depends(get_db), _: Usuario = Depends(solo_admin),
):
    traer(db, Categoria, datos.categoria_id, "categoría")
    prod = Producto(
        **datos.model_dump(),
        orden=srv.siguiente_orden(db, Producto.orden, Producto.categoria_id == datos.categoria_id),
    )
    prod.nombre = prod.nombre.strip()
    db.add(prod)
    return guardar(db, avisos, prod)


@router.patch("/productos/{producto_id}", response_model=ProductoAdmin)
def editar_producto(
    producto_id: int, cambios: ProductoCambios, avisos: BackgroundTasks,
    db: Session = Depends(get_db), _: Usuario = Depends(solo_admin),
):
    prod = traer(db, Producto, producto_id, "producto")
    if cambios.categoria_id is not None and cambios.categoria_id != prod.categoria_id:
        traer(db, Categoria, cambios.categoria_id, "categoría")
        prod.orden = srv.siguiente_orden(db, Producto.orden, Producto.categoria_id == cambios.categoria_id)
    # descripcion y etiqueta se pueden vaciar mandando null
    srv.aplicar_cambios(prod, cambios, campos_con_null=("descripcion", "etiqueta"))
    return guardar(db, avisos, prod)


@router.delete("/productos/{producto_id}", status_code=204)
def borrar_producto(
    producto_id: int, avisos: BackgroundTasks,
    db: Session = Depends(get_db), _: Usuario = Depends(solo_admin),
):
    # Los pedidos viejos no se rompen: tienen nombre y precio copiados
    db.delete(traer(db, Producto, producto_id, "producto"))
    guardar(db, avisos)
    return Response(status_code=204)


@router.patch("/productos/{producto_id}/disponible", response_model=ProductoAdmin)
def disponibilidad_producto(
    producto_id: int, datos: Disponibilidad, avisos: BackgroundTasks,
    db: Session = Depends(get_db), _: Usuario = Depends(admin_o_cantina),
):
    prod = traer(db, Producto, producto_id, "producto")
    prod.disponible = datos.disponible
    return guardar(db, avisos, prod)


# ---------- grupos de opciones ----------


@router.post("/productos/{producto_id}/grupos", response_model=GrupoAdmin, status_code=201)
def crear_grupo(
    producto_id: int, datos: GrupoNuevo, avisos: BackgroundTasks,
    db: Session = Depends(get_db), _: Usuario = Depends(solo_admin),
):
    traer(db, Producto, producto_id, "producto")
    grupo = GrupoOpciones(
        producto_id=producto_id, **datos.model_dump(),
        orden=srv.siguiente_orden(db, GrupoOpciones.orden, GrupoOpciones.producto_id == producto_id),
    )
    db.add(grupo)
    return guardar(db, avisos, grupo)


@router.patch("/grupos/{grupo_id}", response_model=GrupoAdmin)
def editar_grupo(
    grupo_id: int, cambios: GrupoCambios, avisos: BackgroundTasks,
    db: Session = Depends(get_db), _: Usuario = Depends(solo_admin),
):
    grupo = traer(db, GrupoOpciones, grupo_id, "grupo")
    srv.aplicar_cambios(grupo, cambios, campos_con_null=("max_selecciones",))
    return guardar(db, avisos, grupo)


@router.delete("/grupos/{grupo_id}", status_code=204)
def borrar_grupo(
    grupo_id: int, avisos: BackgroundTasks,
    db: Session = Depends(get_db), _: Usuario = Depends(solo_admin),
):
    db.delete(traer(db, GrupoOpciones, grupo_id, "grupo"))
    guardar(db, avisos)
    return Response(status_code=204)


# ---------- opciones ----------


@router.post("/grupos/{grupo_id}/opciones", response_model=OpcionAdmin, status_code=201)
def crear_opcion(
    grupo_id: int, datos: OpcionNueva, avisos: BackgroundTasks,
    db: Session = Depends(get_db), _: Usuario = Depends(solo_admin),
):
    traer(db, GrupoOpciones, grupo_id, "grupo")
    op = Opcion(
        grupo_id=grupo_id, **datos.model_dump(),
        orden=srv.siguiente_orden(db, Opcion.orden, Opcion.grupo_id == grupo_id),
    )
    db.add(op)
    return guardar(db, avisos, op)


@router.patch("/opciones/{opcion_id}", response_model=OpcionAdmin)
def editar_opcion(
    opcion_id: int, cambios: OpcionCambios, avisos: BackgroundTasks,
    db: Session = Depends(get_db), _: Usuario = Depends(solo_admin),
):
    op = traer(db, Opcion, opcion_id, "opción")
    srv.aplicar_cambios(op, cambios, campos_con_null=("cantidad_max",))
    return guardar(db, avisos, op)


@router.delete("/opciones/{opcion_id}", status_code=204)
def borrar_opcion(
    opcion_id: int, avisos: BackgroundTasks,
    db: Session = Depends(get_db), _: Usuario = Depends(solo_admin),
):
    db.delete(traer(db, Opcion, opcion_id, "opción"))
    guardar(db, avisos)
    return Response(status_code=204)


@router.patch("/opciones/{opcion_id}/disponible", response_model=OpcionAdmin)
def disponibilidad_opcion(
    opcion_id: int, datos: Disponibilidad, avisos: BackgroundTasks,
    db: Session = Depends(get_db), _: Usuario = Depends(admin_o_cantina),
):
    op = traer(db, Opcion, opcion_id, "opción")
    op.disponible = datos.disponible
    return guardar(db, avisos, op)


# ---------- aumento de precios ----------


@router.post("/aumento/vista-previa", response_model=VistaPreviaAumento)
def vista_previa_aumento(
    datos: AumentoPrecios, db: Session = Depends(get_db), _: Usuario = Depends(solo_admin),
):
    # No guarda nada: es para que Renzo vea cómo quedan antes de aplicar
    try:
        return srv.calcular_aumento(db, datos)
    except srv.CartaInvalida as e:
        raise error(e)


@router.post("/aumento/aplicar", response_model=VistaPreviaAumento)
def aplicar_aumento(
    datos: AumentoPrecios, avisos: BackgroundTasks,
    db: Session = Depends(get_db), _: Usuario = Depends(solo_admin),
):
    try:
        resultado = srv.aplicar_aumento(db, datos)
    except srv.CartaInvalida as e:
        raise error(e)
    avisos.add_task(avisar_carta)
    return resultado
