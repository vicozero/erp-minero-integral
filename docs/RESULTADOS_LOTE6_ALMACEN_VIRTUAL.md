# Resultados — Lote 6: almacén virtual interactivo 2D/3D

**Fecha:** 19/11/2026
**Estado:** validado localmente con datos sintéticos. **No se declara producción.**
**Repositorio:** `E:\ERP_MINERO`. Sin `push`, sin despliegue, sin conexión a CONTPAQi ni Sierra Madre GMAO.

## 1. Objetivo y punto de partida

Convertir el plano 2D existente en una herramienta visual conectada al WMS real: vista superior interactiva, escena 3D derivada de la jerarquía `mdm.storage_location`, ficha de inventario transaccional y tablero de alertas, conservando el plano referencial versionado y el RBAC vigente.

| Métrica | Antes del Lote 6 | Después del Lote 6 |
|---|---:|---:|
| Pruebas backend | 127 | **133** |
| Pruebas frontend | 41 | **49** |
| Pantallas nuevas | — | 1 (`/almacen-virtual`) |
| Endpoints WMS nuevos | — | 3 (inventario, dashboard, búsqueda) |
| Migraciones nuevas | — | **ninguna** |

La base conceptual y el inventario de las 14 imágenes de referencia están en `docs/ANALISIS_REFERENCIAS_ALMACEN_2D_3D.md`. Ninguna imagen se modificó ni se usó como plano exacto; se detectó un duplicado byte a byte (`4e3878ec…` ≡ `ddcdf2de…`) y se documentó sin eliminar archivos.

## 2. Cambios entregados

### Backend

- `app/modules/inventory/wms_dashboard_schemas.py` (nuevo): proyecciones de sólo lectura `LocationInventoryOut`, `WarehouseDashboardOut` y `MaterialSearchResultOut`. Ningún esquema permite escribir saldos.
- `app/modules/inventory/wms_dashboard_service.py` (nuevo): construye la ficha, el tablero y la búsqueda desde `inv.stock_balance`, `inv.stock_movement`, `mdm.storage_location`, lotes, series, restricciones y cross-references. Disponible = físico − reservado. El costo se incluye sólo cuando el actor tiene `warehouse.stock.view`.
- `app/api/v1/routers/wms.py`:
  - `GET /api/v1/wms/locations/{id}/inventory` — `warehouse.location.view`.
  - `GET /api/v1/wms/dashboard` — `warehouse.map.view`; filtros `warehouse_id`, `zone`, `family_id`.
  - `GET /api/v1/wms/materials/search` — `catalog.view`; búsqueda por código, descripción, número de parte, código interno y familia.
  - Los tres reutilizan `_allowed_warehouses()`; el alcance por almacén se aplica en las consultas.
- `wms_map_schemas.py` / `wms_map_service.py`: los nodos del plano ahora exponen `capacity_qty`, para colorear por ocupación real sin inventar capacidad.

### Frontend

- `src/features/wms/WarehouseInteractive.tsx` (nuevo): pantalla con menú lateral, barra de herramientas, selector de almacén, filtros, conmutador 2D/3D, buscador, KPIs, área central, panel lateral redimensionable y contraíble, leyenda y estados de carga/error.
- `src/features/wms/InteractiveMap2D.tsx` (nuevo): plano superior con zoom, desplazamiento, colores por ocupación, etiquetas, resaltado de búsqueda y selección sincronizada. Aviso permanente de plano referencial.
- `src/features/wms/Warehouse3D.tsx` (nuevo): `Canvas` de React Three Fiber + `OrbitControls`/`Html` de Drei. Piso, pasillos implícitos, estructuras de rack, niveles, posiciones y cajas ilustrativas **derivadas de los nodos WMS**. Sin racks ficticios. Rotar, zoom, desplazar, seleccionar rack/nivel/posición, vista general/detallada, restablecer cámara y parámetros geométricos referenciales ajustables.
- `src/features/wms/SceneErrorBoundary.tsx`, `webgl.ts` y `warehouse3dConfig.ts` (nuevos): fallback 2D, detección de WebGL y parámetros referenciales separados del componente 3D.
- `src/api/types.ts`, `src/api/client.ts`, `src/auth/permissions.ts`, `src/App.tsx`, `src/components/Layout.tsx` y `src/styles.css`: tipos, métodos, permisos `VIEW_MAPS`/`VIEW_STOCK_COST`, ruta `/almacen-virtual`, menú «Almacén Virtual 2D/3D» y estilos empresariales.
- Dependencias fijadas para React 18.3.1: `@react-three/fiber@8.18.0`, `@react-three/drei@9.122.0`, `three@0.169.0` y `@types/three@0.169.0`. La escena 3D se importa con `lazy()` y genera un chunk independiente.

## 3. Verificación ejecutada

```powershell
cd E:\ERP_MINERO\backend
python -m ruff check app tests
python -m mypy app --follow-imports=silent
python -m pytest -q
python -m alembic upgrade head

cd E:\ERP_MINERO\frontend
npx.cmd tsc --noEmit -p tsconfig.json
npm.cmd run test -- --run
npm.cmd run build
```

Resultados:

- `ruff check app tests`: **All checks passed**.
- `mypy app --follow-imports=silent`: **Success: no issues found in 82 source files**.
- Backend: **133 passed** (127 anteriores + 6 nuevos de `tests/test_wms_interactivo.py`).
- Alembic: `head` alcanzado; **no se creó ninguna migración**.
- `tsc --noEmit`: sin errores. Frontend: **49 passed** (41 anteriores + 8 nuevos de `WarehouseInteractive.test.tsx`).
- `npm run build`: correcto. Chunk principal 333.8 kB y chunk 3D 847.7 kB (cargado bajo demanda).

Las pruebas nuevas cubren: inventario con fuentes reales, costo restringido por permiso, estado vacío, separación entre estado de ubicación/ocupación/stock bajo mínimo, búsqueda con ubicaciones a resaltar, RBAC de los tres endpoints, independencia entre almacenes, correspondencia de identificadores 2D↔3D y fallback cuando WebGL no está disponible.

## 4. Validación real en el portal

Sesión autenticada en **`http://localhost:5173/almacen-virtual`** con la credencial de desarrollo leída sólo desde `var/secrets/admin_dev_credential.txt` (ignorada por Git; valor nunca impreso). Backend en `127.0.0.1:8000`, sin exposición a red.

1. El plano mostró 6 ubicaciones, 3 ocupadas, 3 vacías y 4 % de capacidad utilizada (240 / 6 000), con seis coordenadas referenciales y sin racks inventados.
2. Al seleccionar `A-01-R1-1-01`, el panel consultó el inventario real: jerarquía `LAG_DEMO / ALM_PRINCIPAL_DEMO / A / 01 / R1 / 1 / 01 / …`, estado `ACTIVE`, físico/reservado/disponible, UOM, número de parte `FF-M8-30`, código interno, costo permitido por el perfil admin y último movimiento.
3. La búsqueda de `TORNILLO` resaltó la ubicación con existencias y mostró `DEMO-TORNILLO` con su número de parte y disponibilidad.
4. La vista 3D renderizó con WebGL 2.0 (ANGLE / Microsoft Basic Render Driver en Chrome headless). Se seleccionó el rack `A / 02 / R1`, luego la posición `A-01-R1-2-01`; el panel reflejó cada selección. Sin errores de página.
5. Las filas demo persistidas no tenían coordenadas (el seed sólo las asigna al crear). Se completaron con los valores sintéticos del seed mediante `PATCH /api/v1/wms/locations/{id}/coordinates`, endpoint ya auditado (`WMS_LOCATION_COORDINATES_UPDATED`). No se modificaron saldos ni se crearon migraciones.

Evidencia real (PNG, `docs/evidencia/`):

| Archivo | Contenido |
|---|---|
| `lote6_01_2d_general.png` | Vista general 2D con KPIs, leyenda y aviso referencial |
| `lote6_02_panel_inventario.png` | Ubicación seleccionada y panel de inventario real |
| `lote6_03_busqueda_refacciones.png` | Búsqueda de refacciones con resaltado 2D |
| `lote6_04_3d_general.png` | Vista general 3D con racks, niveles y posiciones |
| `lote6_05_3d_rack_seleccionado.png` | Rack `A / 02 / R1` seleccionado |
| `lote6_06_3d_posicion_seleccionada.png` | Posición `A-01-R1-2-01` seleccionada |

## 5. Decisiones respetadas

- **Sin racks ficticios:** cada objeto 3D proviene de una fila existente de `mdm.storage_location`; sin coordenadas, la ubicación no se dibuja.
- **Geometría referencial:** anchos, profundidades y alturas son ajustables en la UI; no se dedujeron medidas físicas de las imágenes.
- **Planos referenciales:** se conservan las versiones, `is_exact=false` y el aviso visual. El editor original sigue disponible dentro del panel, plegado por defecto.
- **Sólo lectura:** ninguna interacción gráfica modifica existencias, reservas ni costos. La única escritura persistente es la edición de coordenadas ya auditada.
- **RBAC:** se reutilizan `warehouse.map.view/manage`, `warehouse.location.view` y `catalog.view`; no se crearon permisos nuevos. El costo exige `warehouse.stock.view`.
- **Sin migración:** no había cambios de esquema que justificarla.

## 6. Limitaciones y siguiente paso

| Pendiente | Situación actual | Acción requerida |
|---|---|---|
| Escala física real | La 3D es referencial y ajustable; no hay cotas del almacén | Levantamiento autorizado y fuente de medidas antes de cualquier uso operativo |
| Imágenes de referencia | Analizadas por OCR y métricas de píxel; sin comparación píxel a píxel | Revisión visual humana de las 14 imágenes y decisión sobre el duplicado detectado |
| WebGL | Si no hay WebGL, se muestra el fallback 2D; un error de render se aísla y vuelve a 2D | Probar en el navegador operativo con aceleración real antes de intranet |
| Dependencias 3D | `npm install` informó 8 avisos (5 moderados, 1 alto, 2 críticos) y deprecación de `three-mesh-bvh@0.7.8` por la versión de `three` | Revisar auditoría y actualizar versiones de forma controlada antes de producción |
| Bundle 3D | ~848 kB en chunk independiente, cargado sólo al activar 3D | Evaluar división adicional si la intranet tiene ancho de banda limitado |
| Datos demo | Coordenadas sintéticas del seed completadas vía API auditada | Confirmar con inventario físico antes de usar el plano para surtido |

No se publicaron puertos, no hubo `git push`, no se conectó a CONTPAQi/GMAO y la credencial administrativa no se versionó. **Siguiente paso:** validar el plano con un levantamiento real autorizado y revisar la auditoría de dependencias; recién después plantear intranet y capacitación a usuarios.
