# Resultados — Almacén virtual (Lote 3)

Fecha: 19/11/2026. Estado: **backend y frontend implementados y probados localmente**. Contrato y decisiones en `docs/ALMACEN_VIRTUAL.md`.

## Decisiones aprobadas

| Tema | Decisión |
|---|---|
| Fondo del plano | Proyección desde `mdm.storage_location`; fondo opcional, nunca por defecto. |
| Etiquetado | Todo fondo se muestra como `Referencial · no es plano exacto`. |
| Exactitud | `is_exact = false` obligatorio por restricción de base. |
| QR | Tokens nuevos opacos `WMS-…`; tokens legacy `WMS:ALM…` intactos. |

## Cambios entregados

### Backend

- Permisos `warehouse.map.view`, `warehouse.map.manage` y alias en español.
- `mdm.storage_location`: `coord_x`, `coord_y` y `parent_id` expuestos; jerarquía derivada en backend.
- `wms.location_map` versionado, con una sola versión activa por almacén e historial append-only.
- Migración aditiva `e5f6a7b8c9d0`; `wms` agregado al arnés de limpieza de pruebas.
- `wms_map_service.py`: proyección de nodos, fondos validados y confinados, coordenadas acotadas al lienzo, QR SVG y resolución por token con alcance por almacén.
- Endpoints `/api/v1/wms/maps/...`, coordenadas, QR y lookup documentados en `docs/ALMACEN_VIRTUAL.md`.
- Dependencia `qrcode>=8.0`.
- Semilla con coordenadas sintéticas y mapa v1 por almacén demo.
- Pruebas en `tests/test_wms_virtual.py`; ajustes en `test_wms_lote_a.py` y en las pruebas de revisión Alembic.

### Frontend

- Tipos y cliente API del mapa, coordenadas y QR.
- Componente `VirtualMap.tsx` integrado en `Locations.tsx`.
- `PERM.MANAGE_MAPS` separado de `MANAGE_LOCATIONS`.
- Estilos del aviso referencial, rejilla, nodos, panel lateral, formularios e historial.
- Pruebas ampliadas en `Locations.test.tsx`: aviso referencial, nodo → panel lateral, guardado de coordenadas, QR opaco y permisos.

## Verificación ejecutada

```powershell
cd E:\ERP_MINERO\backend
python -m ruff check app tests
python -m mypy app --follow-imports=silent
python -m pytest -o addopts="" -q
python -m alembic upgrade base:head --sql

cd E:\ERP_MINERO\frontend
npm.cmd run test -- --run
npm.cmd run build
```

Resultados:

- `ruff check app tests`: **sin errores**.
- `mypy app --follow-imports=silent`: **sin errores en 79 archivos**.
- Backend: **114 pruebas aprobadas** sobre PostgreSQL `erp_minero_test`; sin SQLite.
- Alembic: `e5f6a7b8c9d0 (head)` aplicado en `erp_minero_test`.
- Generación offline `base:head`: las 11 revisiones se renderizan en orden; 58 `CREATE TABLE`, 0 `DROP TABLE`, 0 `DELETE FROM` y ningún `TRUNCATE` ejecutable (sólo la definición del disparador que lo prohíbe).
- Frontend: **30 pruebas aprobadas** en 8 archivos y compilación de producción correcta.
- Cobertura nueva: proyección referencial, coordenadas con auditoría y sin tocar saldos, fondos versionados con SHA-256, rechazo de `is_exact = true` en base, QR opaco con resolución y permisos, y UI con aviso/panel/guardado/permisos.

## Cadena de custodia

- Nodos derivados de la ubicación en cada consulta: el mapa no duplica inventario ni es oficial.
- Toda versión de fondo registra SHA-256, tamaño, actor y `is_exact = false` en bitácora; si falla la creación de versión o la auditoría, se elimina el archivo recién escrito.
- El cambio de coordenadas es auditable y no modifica `inv.stock_balance` ni genera movimientos.
- El backend revalida permisos y alcance por almacén aunque el frontend oculte controles.

## Limitaciones conocidas

1. No se pudo ejecutar literalmente `empty → head` en una base nueva: el usuario de PostgreSQL no tiene `CREATEDB`. Se verificó la generación SQL offline de toda la cadena y la aplicación incremental en `erp_minero_test`.
2. La base de desarrollo `erp_minero_dev` permanece en la revisión anterior (`a1b2c3d4e5f6`); no se modificó sin autorización.
3. Sin captura móvil, escaneo con cámara ni órdenes de movimiento (D-06 sigue sin aprobarse).
4. El fondo es referencial; no hay validación contra el almacén físico.
5. No se conectó a CONTPAQi ni GMAO y no se usaron datos reales.
6. No se publicaron puertos, no hubo `push` y no se declara apto para producción.

## Siguiente paso

Ejecutar la regresión integral documental → SLA → almacén virtual, actualizar `README.md` y decidir si se autoriza `alembic upgrade head` sobre `erp_minero_dev`.
