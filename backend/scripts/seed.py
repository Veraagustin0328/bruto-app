"""
Carga la carta de BRUTO y crea el usuario admin.

Uso (parado en backend, con el venv activado):
    python -m scripts.seed

Si la carta ya está cargada no la duplica, solo te deja crear el admin.
"""
from decimal import Decimal
from getpass import getpass

from sqlalchemy import select

from app.database import SessionLocal
from app.models import Categoria, GrupoOpciones, Opcion, Producto, Rol, TipoGrupo, Usuario
from app.security import hashear_password

# Precios de octubre 2026. Después los cambia Renzo desde el panel
EXTRA_CARNE_QUESO = 2500

# La veggie todavía no tiene precio confirmado, la dejo en 0 y apagada
PRECIO_VEGGIE = 0


def grupo_tamanio(precio_simple, precio_doble):
    # El precio base del producto es el simple, el doble suma la diferencia
    return GrupoOpciones(
        nombre="Tamaño",
        tipo=TipoGrupo.unica,
        obligatorio=True,
        max_selecciones=1,
        orden=0,
        opciones=[
            Opcion(nombre="Simple", precio_extra=Decimal(0), cantidad_max=1, orden=0),
            Opcion(
                nombre="Doble",
                precio_extra=Decimal(precio_doble - precio_simple),
                cantidad_max=1,
                orden=1,
            ),
        ],
    )


def grupo_agregados():
    return GrupoOpciones(
        nombre="Agregados",
        tipo=TipoGrupo.multiple,
        obligatorio=False,
        max_selecciones=None,
        orden=1,
        opciones=[
            # cantidad_max None = pueden pedir las que quieran
            Opcion(
                nombre="Extra carne y queso",
                precio_extra=Decimal(EXTRA_CARNE_QUESO),
                cantidad_max=None,
                orden=0,
            ),
        ],
    )


def grupo_veggie():
    return GrupoOpciones(
        nombre="Opción veggie",
        tipo=TipoGrupo.unica,
        obligatorio=False,
        max_selecciones=1,
        orden=2,
        opciones=[
            # Apagada hasta que Renzo confirme el precio
            Opcion(
                nombre="Medallón veggie",
                precio_extra=Decimal(PRECIO_VEGGIE),
                cantidad_max=1,
                disponible=False,
                orden=0,
            ),
        ],
    )


def burger(nombre, descripcion, simple, doble=None, etiqueta=None, orden=0):
    grupos = []
    if doble is not None:
        grupos.append(grupo_tamanio(simple, doble))
    grupos.append(grupo_agregados())
    grupos.append(grupo_veggie())

    return Producto(
        nombre=nombre,
        descripcion=f"{descripcion}. Con papas fritas.",
        precio=Decimal(simple),
        etiqueta=etiqueta,
        orden=orden,
        grupos=grupos,
    )


def simple(nombre, precio, descripcion=None, orden=0, **extra):
    return Producto(
        nombre=nombre, descripcion=descripcion, precio=Decimal(precio), orden=orden, **extra
    )


def armar_carta():
    burgers = Categoria(
        nombre="Smash Burgers",
        orden=0,
        productos=[
            burger(
                "Cuarto de Libra",
                "Carne smasheada, doble cheddar, cebolla brunoise, pepinillos, mostaza y ketchup",
                12500, 14500, orden=0,
            ),
            burger(
                "Clásica",
                "Carne smasheada, doble cheddar, lechuga, tomate, cebolla morada, mostaza, ketchup y lactonesa",
                12500, 14500, orden=1,
            ),
            burger(
                "Criolla",
                "Carne smasheada, queso provolone, salsa criolla, chimichurri y lactonesa",
                13000, 14500, orden=2,
            ),
            burger(
                "Animal",
                "Carne smasheada, doble cheddar, cebolla caramelizada, panceta ahumada, pepinillos y extra salsa BRT",
                13500, 15000, etiqueta="Recomendada", orden=3,
            ),
            burger(
                "Big Pollo",
                "Medallón de pollo frito, cheddar x2, lechuga, cebolla, salsa BRT y ketchup",
                12500, orden=4,
            ),
        ],
    )

    ahumados = Categoria(
        nombre="Sandwiches Ahumados",
        orden=1,
        productos=[
            simple(
                "Bondiola Ahumada", 16500,
                "En pan ciabatta de 20 cm. Queso provolone, coleslaw, tomate y lactonesa", orden=0,
            ),
            simple(
                "Ternera Ahumada", 18000,
                "En pan ciabatta de 20 cm. Queso provolone, coleslaw, tomate y lactonesa", orden=1,
            ),
            simple(
                "Lomo Clásico", 19000,
                "Jamón, queso, lechuga, salsa de tomate y lactonesa", orden=2,
            ),
        ],
    )

    pizzas = Categoria(
        nombre="Pizzas",
        orden=2,
        productos=[
            simple("Muzzarella", 14000, "Masa madre. Mozzarella y aceitunas", orden=0),
            simple(
                "Especial", 16000,
                "Masa madre. Mozzarella, jamón, morrones asados y aceitunas", orden=1,
            ),
            # Se ve en la carta pero todavía no se puede pedir
            simple(
                "Pepperoni", 16000,
                "Masa madre. Mozzarella, pepperoni y aceitunas", orden=2,
                etiqueta="Próximamente", disponible=False,
            ),
        ],
    )

    para_picar = Categoria(
        nombre="Para Picar",
        orden=3,
        productos=[
            simple("Papas Fritas", 9000, orden=0),
            simple("Fingers de Pollo", 12500, orden=1),
            simple("Ensalada de Pollo", 9000, orden=2),
            simple("Super Pancho", 4000, "Con lluvia de papas", orden=3),
        ],
    )

    return [burgers, ahumados, pizzas, para_picar]


def cargar_carta(db):
    if db.scalar(select(Categoria).limit(1)):
        print("La carta ya está cargada, no la toco.")
        return

    db.add_all(armar_carta())
    db.commit()
    print("Carta de BRUTO cargada.")


def crear_admin(db):
    if db.scalar(select(Usuario).where(Usuario.rol == Rol.admin).limit(1)):
        print("Ya hay un admin, no creo otro.")
        return

    print("\nCreando el usuario admin:")
    nombre = input("  Nombre: ").strip()
    email = input("  Email: ").strip().lower()
    password = getpass("  Contraseña (no se ve mientras escribís): ")

    if len(password) < 8:
        print("La contraseña tiene que tener al menos 8 caracteres. Corré el seed de nuevo.")
        return

    db.add(
        Usuario(
            nombre=nombre,
            email=email,
            password_hash=hashear_password(password),
            rol=Rol.admin,
        )
    )
    db.commit()
    print(f"Admin {email} creado.")


def main():
    with SessionLocal() as db:
        cargar_carta(db)
        crear_admin(db)


if __name__ == "__main__":
    main()
