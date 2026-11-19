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

> En el entorno actual PostgreSQL 17 está instalado y activo en `127.0.0.1:5432`; el perfil local apunta a `erp_minero_dev`. Para un piloto se debe crear una base independiente con autorización formal.

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

Para detener y reiniciar la API y el proxy local sin afectar al servidor Vite:

```powershell
cd E:\ERP_MINERO
python scripts/portal_ctl.py restart
python scripts/portal_ctl.py stop
```

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

Además existe la cuenta maestra `admin` con rol `SUPERADMIN`, creada con el comando `python -m app.modules.identity.bootstrap_admin` sobre `erp_minero_dev`. Su contraseña inicial era temporal y ya fue rotada durante la validación; la credencial vigente no se guarda en el repositorio. El comando solo puede ejecutarse sobre la base de desarrollo y exige cambio de contraseña en el primer acceso.

## Pruebas

```powershell
cd E:\ERP_MINERO\backend
pytest -q

cd E:\ERP_MINERO\frontend
npm.cmd run test -- --run
npm.cmd run build
```

Resultados obtenidos en el entorno de desarrollo:

- Backend: 123 pruebas aprobadas con PostgreSQL real (`erp_minero_test`); no se usa SQLite.
- Backend: `ruff check app tests` y `mypy app --follow-imports=silent` sin errores.
- Frontend: 32 pruebas aprobadas y compilación de producción correcta.

Las pruebas requieren `DATABASE_URL` y aplican migraciones Alembic antes de ejecutarse; el arnés solo permite la base `erp_minero_test` y restaura datos sintéticos.

## Flujo funcional cubierto

1. Solicitante crea requisición con varias partidas y la envía.
2. Aprobador autoriza total o parcialmente, o rechaza con motivo.
3. Almacenista consulta disponibilidad, reserva sin descontar y entrega parcialmente.
4. Cada entrega descarta existencias solo al confirmarse y genera kardex.
5. Comprador genera OC por faltantes, la aprueba y registra recepciones parciales.
6. Las recepciones entran a inventario y permiten completar entregas pendientes.
7. Todas las operaciones quedan en bitácora y con número de documento único.
8. Los vales de salida y las requisiciones se exportan a PDF/XLSX con plantillas versionadas, folio único y reimpresión de la versión emitida; la descarga no mueve inventario.
9. El semáforo SLA calcula en backend el color de cada requisición, conserva historial inmutable y se muestra en el portal como indicador separado del estado administrativo.
10. El almacén virtual proyecta la jerarquía unidad → almacén → zona → pasillo → rack → nivel → posición sobre un plano 2D referencial, con panel lateral, QR opaco y coordenadas auditables que no modifican existencias.

Detalle de formatos: `docs/VALES_ALMACEN_FORMATOS.md`, `docs/REQUISICIONES_FORMATOS.md`, `docs/RESULTADOS_MODULO_DOCUMENTAL.md` y evidencias en `docs/EVIDENCIA_FORMATOS/`.
Detalle del semáforo: `docs/SLA_SEMAFORO.md` y `docs/RESULTADOS_SEMAFORO_SLA.md`.
Detalle del almacén virtual: `docs/ALMACEN_VIRTUAL.md` y `docs/RESULTADOS_ALMACEN_VIRTUAL.md`.
Detalle de seguridad Lote 4: `docs/RESULTADOS_LOTE4_SEGURIDAD.md`.

## Estado de implementación

Implementado y probado localmente: infraestructura FastAPI/SQLAlchemy/Alembic, autenticación RBAC con bitácora, requisiciones con folios y decisiones, inventario operativo con reservas/entregas/kardex, compras con recepciones parciales e idempotencia, formatos VA/REQ versionados, semáforo SLA con historial y filtros, almacén virtual con plano 2D referencial/QR, e interfaz React con menú lateral, dashboard y pantallas por dominio.

Pendiente para considerar la entrega completa en producción local:

1. Crear `erp_minero_pilot` en `127.0.0.1` con autorización formal y perfil `.env` propio; nunca reutilizar credenciales de desarrollo.
2. Ejecutar `alembic upgrade head` y sembrar solo datos sintéticos en esa base. La base `erp_minero_dev` ya está en `e5f6a7b8c9d0 (head)` y cuenta con respaldo verificable.
3. Ejecutar la prueba de concurrencia transaccional (actualmente omitida) con dos sesiones reales.
4. Definir la política de rotación de la credencial maestra y de sesiones antes de cualquier uso fuera de desarrollo.
5. Autorizar captura móvil, órdenes de movimiento (D-06), plano exacto y pantallas de reportes/presupuestos/configuración/integraciones, si se requieren.

Ninguna función se considera terminada sin sus pruebas ejecutadas.
