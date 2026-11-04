# Decisiones de la Tarea 1 (backend)

Todo se hizo en la rama `backend-pendientes`. Main no se tocó, no se hizo push ni deploy, no se tocó el `.env` ni la base de Docker.

## Tests de lo que ya andaba (antes de B1)

- Tests con pytest en `backend/tests/`, contra SQLite en memoria. Las variables de entorno se pisan en `tests/conftest.py` antes de importar la app, así no leen el `.env` (y nunca usan el token de MP real).
- La carta de los tests es la del seed (`armar_carta()`), así los precios son los reales de BRUTO.
- **Cambio chico en el backend:** `inicio_jornada()` ahora devuelve la hora en UTC (la misma hora, otra zona). En Postgres no cambia nada, pero SQLite compara fechas como texto y la numeración del día se corría 3 horas. Sin esto no se podía testear bien.
- `pytest` y `httpx` quedaron en `backend/requirements.txt` (la tarea pide un solo requirements).
