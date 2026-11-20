# Resultados — Lote 7: diseñador profesional de planos 2D/3D

**Fecha:** 19/11/2026
**Estado:** validado localmente con datos sintéticos. **No se declara producción.**
**Repositorio:** `E:\ERP_MINERO`. Sin `push`, sin despliegue, sin conexión a CONTPAQi ni Sierra Madre GMAO.

## 1. Objetivo y punto de partida

Convertir `Almacén Virtual 2D/3D` en un diseñador visual integrado al ERP: dibujar, editar, guardar, publicar, recargar y visualizar **un único modelo de escena** en 2D y 3D, con posiciones vinculadas al WMS real sin convertirse en un segundo inventario oficial.

| Métrica | Antes del Lote 7 | Después del Lote 7 |
|---|---:|---:|
| Pruebas backend | 133 | **141** |
| Pruebas frontend | 49 | **58** |
| Endpoints WMS nuevos | — | **7** (`/wms/plans…`) |
| Permisos nuevos | — | **3** (`warehouse.plan.view/draft/publish`) |
| Migraciones nuevas | — | **1** (`a2b3c4d5e6f7`) |
| Pantallas nuevas | — | 1 modal diseñador dentro de `/almacen-virtual` |

La base conceptual y el inventario de las 14 imágenes de referencia están en `docs/ANALISIS_REFERENCIAS_ALMACEN_2D_3D.md`. El plano sigue siendo **referencial**: no se dedujeron medidas físicas ni se declaró precisión de levantamiento.

## 2. Cambios entregados

### Backend

- `app/modules/inventory/models.py` (nuevo): `FloorPlan` con `elements` JSONB, `status`, `plan_version`, `revision`, `location_refs`, `is_active` y unicidad de borrador por almacén (`uq_floor_plan_draft`).
- `migrations/versions/a2b3c4d5e6f7_lote7_disenador_planos.py` (nueva): migración **aditiva**, `down_revision = f7a8b9c0d1e2`; `downgrade` bloqueado explícitamente. Aplicada en la base de desarrollo.
- `app/modules/inventory/wms_designer_schemas.py` (nuevo): contratos Pydantic v2 para escena, guardado, publicación, rack, importación y exportación. Límites: **1000 elementos**, **500 posiciones por rack** y `NUMERIC` para todas las coordenadas y dimensiones.
- `app/modules/inventory/wms_designer_service.py` (nuevo): workspace de sólo lectura, borrador idempotente, guardado con **concurrencia optimista** (`revision`, conflicto HTTP 409), publicación *append-only* con clonación del borrador, asistente de racks, importación validada y exportación segura. Las posiciones WMS se crean únicamente mediante `WmsCatalogService.create_location`.
- `app/api/v1/routers/wms_designer.py` (nuevo):

  | Endpoint | Permiso |
  |---|---|
  | `GET /api/v1/wms/plans/workspace` | `warehouse.plan.view` o `warehouse.map.view` |
  | `POST /api/v1/wms/plans/draft` | `warehouse.plan.draft` |
  | `PUT /api/v1/wms/plans/{plan_id}` | `warehouse.plan.draft` |
  | `POST /api/v1/wms/plans/{plan_id}/publish` | `warehouse.plan.publish` |
  | `POST /api/v1/wms/plans/{plan_id}/racks` | `warehouse.plan.draft` (+ `warehouse.location.manage` para vincular) |
  | `POST /api/v1/wms/plans/import-preview` | `warehouse.plan.draft` |
  | `GET /api/v1/wms/plans/{plan_id}/export` | `warehouse.plan.view` o `warehouse.map.view` |

- `app/shared/constants.py` y `app/main.py`: permisos y registro del router. `warehouse.plan.publish` queda reservado a ADMIN/SUPERADMIN.
- Auditoría en la misma transacción: `WMS_PLAN_DRAFT_CREATED`, `WMS_PLAN_DRAFT_SAVED`, `WMS_PLAN_PUBLISHED` y `WMS_PLAN_RACK_CREATED`.

### Frontend

- `src/features/wms/designer/Designer.tsx` (nuevo): orquestador con modos Consulta/Diseño/Operación, historial deshacer/rehacer, copiar/pegar, alineación, capas, guardado, publicación y paneles plegables.
- `src/features/wms/designer/DesignerCanvas.tsx` (nuevo): lienzo SVG propio con cuadrícula configurable, snap, guías, zoom, pan, selección múltiple, arrastre, dibujo de 16 tipos de elemento y medición.
- `src/features/wms/designer/Designer3D.tsx` (nuevo): escena R3F/Three.js reutilizada, con `Suspense`, `Html` de Drei, selección 3D sobre la malla, cámaras orbital/superior/isométrica/frontal/pasillo, ocultar paredes y reset.
- `src/features/wms/designer/RackWizard.tsx` (nuevo): módulos, niveles, posiciones, dimensiones, orientación, capacidad validada, materiales/QR y previsualización 2D/3D; crea y vincula ubicaciones WMS.
- `src/features/wms/designer/PropertiesPanel.tsx` (nuevo): propiedades completas, capa, bloqueo, `dimensions_verified`, vinculación WMS y ficha real con existencias; el costo y el último movimiento sólo se muestran si hay artículos y el perfil tiene `warehouse.stock.view`.
- `src/features/wms/designer/designer.css` (nuevo): corrige el modal de 520 px heredado del CSS global, el apilamiento de controles, el ancho del selector de cámara y la barra horizontal; evita ocultar el asistente en ventanas estrechas.
- `src/features/wms/WarehouseInteractive.tsx`: botón **Editar plano** (`data-testid="editar-plano"`).
- `src/api/client.ts`, `src/api/types.ts`, `src/auth/permissions.ts`: métodos, tipos y permisos del diseñador.

## 3. Verificación ejecutada

```powershell
cd E:\ERP_MINERO\backend
python -m ruff check app tests
python -m mypy app
python -m pytest -q
python -m alembic upgrade head

cd E:\ERP_MINERO\frontend
node node_modules/typescript/bin/tsc --noEmit
node node_modules/vitest/vitest.mjs run
node node_modules/typescript/bin/tsc -b
node node_modules/vite/bin/vite.js build
```

Resultados:

- `ruff check app tests`: **All checks passed**.
- `mypy app`: **Success: no issues found in 85 source files**.
- Backend: **141 passed** (133 anteriores + 8 nuevos de `tests/test_wms_designer.py`). El primer intento del suite completo falló porque el servicio `postgresql-x64-17` estaba detenido; tras iniciarlo, **todas las pruebas pasaron** sin cambios de código.
- Alembic: `head = a2b3c4d5e6f7`; migración probada de `empty` a `head` en `erp_minero_test`.
- `tsc --noEmit` y `tsc -b`: sin errores.
- Frontend: **58 passed** en 14 archivos (49 anteriores + 8 de `Designer.test.tsx` + 1 de `WarehouseInteractive.test.tsx`).
- `vite build`: correcto. Chunk principal 380.6 kB; chunks 3D independientes `Warehouse3D` 4.96 kB y `Designer3D` 2.13 kB, más `OrbitControls` 842.9 kB bajo demanda.

Las pruebas nuevas cubren creación/edición/guardado y recuperación, publicación, deshacer/rehacer, asistente de rack, vinculación WMS, permisos, sincronía 2D↔3D, aislamiento entre almacenes, geometrías inválidas, conflicto de revisión, idempotencia del borrador, **workspace de sólo lectura** y no modificación de `inv.stock_balance`.

## 4. Validación real en el portal

Sesión autenticada en **`http://localhost:5173/almacen-virtual`**. Backend en `127.0.0.1:8000`; credencial de desarrollo leída desde `var/secrets/admin_dev_credential.txt` (ignorada por Git, valor nunca impreso ni versionado). El servidor efímero de credencial en `127.0.0.1:8099` fue detenido al finalizar.

1. Se dibujaron y movieron elementos sobre el lienzo SVG; el rack demostrativo `RACK-L7-DEMO` pasó de `x=0.1953125, y=150` a `x=80.1953125, y=210`.
2. El asistente creó `RACK-L7-CAP` con **Capacidad validada** marcada mediante clic real. La ubicación resultante `RACK-L7-CAP-01-01-01` quedó con `capacity_qty = 25.000000` en el WMS, no con cero.
3. Guardado real: borrador `2d20ad27-0c85-4526-804d-6247ba687f56`, revisión 4, 18 elementos y 12 posiciones vinculadas. Dos llamadas a `POST /draft` devolvieron **el mismo id**, confirmando idempotencia.
4. Recarga real: el editor reabrió la revisión 4 con los 18 elementos persistidos.
5. Vista 3D: 18 etiquetas `data-designer-element-3d` renderizadas; presets `top`, `isometric` y `aisle`, interruptor **Paredes**, **Restablecer cámara** y selección 3D funcionando. Al seleccionar `RACK-L7-DEMO-01-01-01`, el panel mostró la jerarquía real `LAG_DEMO / ALM_PRINCIPAL_DEMO / A / 01 / 01 / N01 / P01 / …` y existencias 0 (sin artículos registrados).
6. Publicación real: **versión 2 PUBLICADA** (`84448d2c-8c8c-405a-81dc-a6b807399e9e`) con 20 elementos y 13 referencias WMS; se creó el borrador clonado **v3** (`f1575e2c-5eff-422f-81e5-8f057d5850dd`) y el aviso `Versión 2 publicada. La edición continúa en un borrador nuevo.`
7. Sin errores de consola durante las interacciones; el aviso `Geometría referencial: no constituye un plano exacto ni modifica inventario.` permanece visible.

Evidencia real (PNG, `docs/evidencia/`):

| Archivo | Contenido |
|---|---|
| `lote7_01_plano_general.png` | Pantalla `/almacen-virtual` con plano referencial y KPIs |
| `lote7_02_editor_abierto.png` | Diseñador abierto desde **Editar plano** |
| `lote7_03_dibujo_2d.png` | Elementos dibujados en el lienzo 2D |
| `lote7_04_rack_niveles.png` | Asistente de rack con módulos y niveles |
| `lote7_05_movimiento.png` | Rack movido con cuadrícula y guías |
| `lote7_06_recarga_persistencia.png` | Recarga con la escena persistida |
| `lote7_07_vista_3d.png` | Vista 3D renderizada y controles de cámara |
| `lote7_08_publicacion.png` | Versión publicada, borrador v3 y aviso |

## 5. Decisiones respetadas

- **Un solo modelo de escena:** 2D y 3D consumen el mismo `elements` JSONB; no hay dos fuentes de verdad gráfica.
- **Inventario oficial sigue siendo CONTPAQi:** el editor crea/vincula ubicaciones WMS, nunca movimientos, reservas ni saldos. No hay conexión a la base de CONTPAQi ni a GMAO.
- **Publicación append-only:** la versión publicada es inmutable; publicar activa esa versión y clona un borrador nuevo.
- **Concurrencia:** revisiones optimistas con HTTP 409; la creación de borrador es idempotente.
- **Trazabilidad:** cada acción sensible queda en la bitácora dentro de la misma transacción.
- **RBAC separado:** consultar planos, editar borradores y publicar son permisos distintos; administrar ubicaciones WMS y consultar costos requieren permisos propios ya existentes.
- **Sin exposición de red:** los servicios escucharon sólo en `127.0.0.1`; no se publicaron puertos ni se modificó el firewall.
- **Sin secretos versionados:** credenciales y evidencia sensible quedan fuera del commit.

## 6. Limitaciones y siguiente paso

| Pendiente | Situación actual | Acción requerida |
|---|---|---|
| Escala y cotas físicas | Geometría referencial; `dimensions_verified` es una declaración del usuario, no una validación documental | Levantamiento autorizado y evidencia antes de uso operativo |
| DXF/DWG | Diferido por decisión del lote | Definir alcance y librería antes de habilitar importación CAD |
| Costos y movimientos en el panel | Sólo se despliegan cuando la ubicación tiene artículos; las posiciones demo están vacías | Validar con una ubicación con existencias reales autorizadas |
| Ventanas muy estrechas | La barra de herramientas se desplaza horizontalmente y el lienzo reduce altura; se corrigió el modal de 520 px y se conservan los paneles | Probar en la resolución real de los puestos antes de intranet |
| Capacidad | La carga sin `capacity_validated` registra capacidad 0 a propósito | Verificar documentalmente antes de usar capacidad para planeación |

No se hizo `git push`, no se declaró producción, no se modificaron saldos y no se conectó con sistemas externos. **Siguiente paso:** revisar el plano con un levantamiento físico autorizado y validar el panel de costos/movimientos en una ubicación con artículos; recién después evaluar intranet y capacitación.
