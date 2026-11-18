# ERP MINERO INTEGRAL

Aplicación web local para gestión de requisiciones, autorizaciones, almacén, compras de prueba y seguimiento por partida.

**Ruta real detectada:** `E:\ERP_MINERO`. La ruta `C:\ERP_MINERO` referida en requerimientos no existe en este entorno.

## Restricciones importantes

- El servicio escucha únicamente en `127.0.0.1`.
- No se abre firewall, no se publican puertos y no se usa `0.0.0.0`.
- No se conecta a CONTPAQi ni a Sierra Madre GMAO.
- Todos los datos son ficticios (`DEMO_*`).
- El inventario del ERP es **operativo**, no oficial. CONTPAQi permanece como sistema oficial.

## Requisitos en Windows

- Python 3.12 o superior.
- Node.js 20 o superior.
- PostgreSQL 16 o superior ejecutándose en `127.0.0.1`.
- Git.

> En el entorno donde se generó este proyecto no había PostgreSQL instalado ni `DATABASE_URL`. El código y las migraciones están preparados; para ejecutar la aplicación se debe proporcionar una base local.

## Arranque del backend

Abrir PowerShell en la raíz del proyecto:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

Copiar `.env.example` a `.env` en la raíz y completar:

```powershell
cd ..
Copy-Item .env.example .env
notepad .env
```

Variables obligatorias:

```text
DATABASE_URL=postgresql+psycopg://erp_local@127.0.0.1:5432/erp_minero
SECRET_KEY=<generar valor propio>
DEMO_PASSWORD=<contraseña ficticia para cuentas demo>
```

Crear la base de datos local (si PostgreSQL está instalado y el usuario tiene permisos):

```powershell
createdb -h 127.0.0.1 -p 5432 -U erp_local erp_minero
```

Aplicar migraciones y semilla ficticia:

```powershell
cd backend
alembic upgrade head
python -m app.db.seed
```

Arrancar API:

```powershell
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Documentación interactiva: <http://127.0.0.1:8000/docs>  
Salud: <http://127.0.0.1:8000/health>

## Arranque del frontend

En otra terminal:

```powershell
cd E:\ERP_MINERO\frontend
npm.cmd install
npm.cmd run dev
```

Si PowerShell bloquea `npm.ps1`, usar siempre `npm.cmd`. La API se toma de `VITE_API_URL` o, por defecto, `http://127.0.0.1:8000`.

Abrir <http://127.0.0.1:5173>. Vite queda enlazado a localhost; no modificar el host.

## Cuentas ficticias

Todas usan la contraseña definida en `DEMO_PASSWORD`:

| Usuario | Rol | Uso |
|---|---|---|
| `demo.admin` | ADMIN | Acceso total |
| `demo.solicitante` | SOLICITANTE | Crear y enviar requisiciones |
| `demo.aprobador` | APROBADOR | Autorizar o rechazar |
| `demo.almacenista` | ALMACENISTA | Reservar, entregar, consultar kardex |
| `demo.comprador` | COMPRADOR | Crear OC, aprobar y recibir |

## Pruebas

```powershell
cd E:\ERP_MINERO\backend
pytest -q

cd E:\ERP_MINERO\frontend
npm.cmd run test -- --run
npm.cmd run build
```

Resultados obtenidos en el entorno de desarrollo:

- Backend: 18 pruebas recopiladas, 17 ejecutadas y aprobadas, 1 omitida (concurrencia transaccional).
- Backend: `ruff check` y `mypy app` sin errores.
- Frontend: 1 prueba aprobada y compilación de producción correcta.

Las pruebas de integración que requieren PostgreSQL se omiten automáticamente si no hay `DATABASE_URL`. La lógica de dominio se prueba con una base SQLite en memoria usando el mismo modelo de datos.

## Flujo funcional cubierto

1. Solicitante crea requisición con varias partidas y la envía.
2. Aprobador autoriza total o parcialmente, o rechaza con motivo.
3. Almacenista consulta disponibilidad, reserva sin descontar y entrega parcialmente.
4. Cada entrega descarta existencias solo al confirmarse y genera kardex.
5. Comprador genera OC por faltantes, la aprueba y registra recepciones parciales.
6. Las recepciones entran a inventario y permiten completar entregas pendientes.
7. Todas las operaciones quedan en bitácora y con número de documento único.

## Estado de implementación

Implementado y probado localmente: infraestructura FastAPI/SQLAlchemy/Alembic, autenticación RBAC con bitácora, requisiciones con folios y decisiones, inventario operativo con reservas/entregas/kardex, compras con recepciones parciales e idempotencia, e interfaz React con menú lateral, dashboard y pantallas por dominio.

Pendiente para considerar la entrega completa en producción local:

1. Instalar PostgreSQL 16+ en `127.0.0.1`, crear la base y completar `DATABASE_URL` en `.env`.
2. Ejecutar `alembic upgrade head` y `python -m app.db.seed` contra esa base.
3. Ejecutar la prueba de concurrencia transaccional (actualmente omitida) con dos sesiones reales.
4. Verificar el flujo completo desde el navegador contra PostgreSQL.

Ninguna función se considera terminada sin sus pruebas ejecutadas.
