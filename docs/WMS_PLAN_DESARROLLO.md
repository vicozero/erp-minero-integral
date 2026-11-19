# WMS avanzado — Plan de desarrollo por lotes

**Fecha:** 2026-11-18

**Estado:** PLAN APROBADO PARA DISEÑO; la ejecución requiere autorización por lote.

**Regla:** un lote a la vez. No desarrollar todos los módulos en una sola ejecución.
**Entrega actual:** documentación de diseño; **no se modificó código operativo**.

---

## 1. Línea base

| Item | Valor |
|---|---|
| Commit local | `c414ee9` |
| Head Alembic | `f4a7c1e2b3d6` |
| Tablas de dominio | 41 + `public.alembic_version` |
| Backend | 63 pruebas, ruff/mypy limpios |
| Frontend | 9 pruebas, build correcto |
| Portal local | 18/18 verificaciones |
| Base piloto | No creada; bloqueo administrativo |
| LAN | No activada |
| CONTPAQi | Sistema oficial; sin conexión directa |

---

## 2. Principios de ejecución

1. **Un lote por commit lógico.** Si un lote es grande, se divide en sub-commits dentro del mismo alcance.
2. **Migración aditiva primero.** Sin `DROP`, `TRUNCATE`, `DELETE` masivo ni `downgrade` sobre datos reales.
3. **Pruebas junto al código.** Toda regla nueva lleva prueba positiva y negativa.
4. **Sin secretos ni datos reales.** Semillas sintéticas con dominio `example.invalid`.
5. **Sin exposición de red.** `127.0.0.1`; LAN sólo con autorización formal.
6. **Sin segundo inventario oficial.** Un solo `inv.stock_movement`.
7. **Sin IA autónoma.** Toda recomendación pasa por humano.
8. **Definición de terminado:** lint, tipos, pruebas, migración `empty → head`, auditoría y documentación.

---

## 3. Secuencia de lotes

```text
Lote A (catálogos y ubicaciones)
   ↓
Lote B (entradas, salidas, devoluciones, kardex)
   ↓
Lote C (traspasos y tránsito)
   ↓
Lote D (inventarios físicos y ajustes)
   ↓
Lote E (herramientas y préstamos)
   ↓
Lote F (costos y valuación)
   ↓
Lote G (móvil, QR y mapa visual)
   ↓
Lote H (IA, analítica y reabastecimiento)
```

Cada lote se cierra con evidencia antes de iniciar el siguiente. Los lotes F–H dependen de decisiones de negocio y volumen de datos.

---

## 4. Detalle por lote

### Lote A — Catálogos, ubicaciones y búsquedas

**Objetivo:** convertir el catálogo básico en maestro WMS y dar identidad física a las ubicaciones, sin tocar el ledger de stock.

**Incluye:**

- familias y atributos de artículo;
- conversiones UOM;
- equivalencias autorizadas;
- relación artículo-proveedor;
- lotes y series maestros;
- ubicaciones jerárquicas con QR;
- restricciones de almacenamiento;
- búsqueda y consultas por ubicación/lote;
- paginación y filtros;
- corrección de deuda técnica de nombres CHECK y vista de cantidades derivadas.

**No incluye:** movimientos, recepciones, traspasos, conteos, costos, móvil ni IA.

**Criterios de aceptación:**

- Migración aditiva de Lote A aplicada de `empty → head`.
- 41 tablas originales intactas; nuevas tablas visibles en `mdm`.
- Búsqueda por código/descripción/familia/proveedor/ubicación con paginación.
- QR único por ubicación y consulta de stock por ubicación con RBAC de almacén.
- Equivalencias requieren aprobador.
- Semilla sintética idempotente.
- Todas las pruebas existentes pasan y se añaden pruebas nuevas.

---

### Lote B — Entradas, salidas, devoluciones y kardex

**Objetivo:** documentar y ejecutar movimientos físicos con tareas, lote/serie/ubicación y kardex valorizado.

**Incluye:** órdenes de movimiento, tareas, recepciones por todas las causas, salidas por OT/equipo, devoluciones, cancelaciones, reversiones y ajustes controlados.

**Dependencias:** Lote A; política de lotes/series; diseño de bloqueos.

**Criterios:** no sobreentrega, no sobrereserva, reversión referenciada, kardex consultable y auditoría completa.

---

### Lote C — Traspasos completos y material en tránsito

**Objetivo:** cubrir traspasos entre ubicaciones, almacenes y unidades mineras con recepción parcial y diferencias.

**Dependencias:** Lote B; aprobación para traspasos entre unidades.

**Criterios:** `TRANSFER_OUT`/`TRANSFER_IN` unidos por `transfer_id`; tránsito separado del disponible; orden determinista de bloqueo; conciliación de diferencias.

---

### Lote D — Inventarios físicos, conteos y ajustes

**Objetivo:** medir y corregir la exactitud del inventario sin alterar hechos previos.

**Incluye:** conteo general, cíclico ABC, por zona, ciego, reconteo, bloqueo de movimientos, aprobación de diferencias y snapshots.

**Criterios:** ajustes autorizados como contrapartida; kardex explica cada diferencia; CONTPAQi no se modifica.

---

### Lote E — Herramientas, préstamos y resguardos

**Objetivo:** controlar herramientas retornables, responsables, calibración y devoluciones parciales.

**Dependencia:** decisión AD-05 (¿`mnt` o subdominio WMS?).

**Criterios:** responsable activo por préstamo; historial append-only; alertas de vencimiento y extravío.

---

### Lote F — Costos, valuación y presupuestos

**Objetivo:** valorizar movimientos y consumos con el método autorizado.

**Dependencia:** decisión formal de Finanzas; no inventar métodos.

**Criterios:** asientos inmutables en la misma transacción; costos por equipo/OT/departamento/centro; aging y obsoletos; conciliación informativa.

---

### Lote G — Captura móvil, QR y mapa visual

**Objetivo:** operar desde dispositivos autorizados con escaneo y evidencia.

**Dependencias:** Lotes A–B; RBAC por almacén; idempotencia probada.

**Criterios:** permisos en backend, QR válido, evidencia con SHA-256, reintento sin duplicados, plano 2D sincronizado; 3D fuera de compromiso inicial.

---

### Lote H — Inteligencia, analítica y reabastecimiento

**Objetivo:** sugerir, predecir y explicar sin actuar automáticamente sobre el inventario.

**Dependencias:** datos sintéticos suficientes; políticas de reabastecimiento aprobadas; Catálogo y movimientos estables.

**Criterios:** recomendaciones con explicación y aprobación humana; abstención cuando falten datos; KPIs auditables; exportación segura.

---

## 5. Matriz de dependencias

| Lote | Depende de | Bloqueo externo |
|---|---|---|
| A | Ninguno técnico | Aprobación de esquema `wms` y jerarquía de ubicación |
| B | A | Definición de lotes/series y reversiones |
| C | B | Traspasos entre unidades mineras |
| D | B/C | Quién aprueba diferencias |
| E | A/B | Modelo de herramientas y responsables |
| F | B | Política contable aprobada |
| G | A/B | Dispositivos y permisos por almacén |
| H | A–F | Volumen de datos y reglas de negocio |

---

## 6. Definición de terminado por lote

Cada lote sólo se declara terminado cuando:

1. `python -m pytest -q` pasa, incluyendo pruebas nuevas.
2. `python -m ruff check .` y `python -m mypy app` pasan.
3. `npm.cmd run test -- --run` y `npm.cmd run build` pasan si hay cambios frontend.
4. `python scripts\verificar_portal.py` sigue en 18/18 o superior.
5. `alembic upgrade head` funciona desde base vacía.
6. No hay secretos ni datos reales en el diff.
7. La bitácora cubre las acciones sensibles nuevas.
8. La documentación del lote queda actualizada.
9. Se reportan limitaciones y siguiente paso.

**No se declara producción.** CONTPAQi sigue siendo oficial y el triple match OC–recepción–factura continúa pendiente hasta su propio lote.

---

## 7. Gestión de riesgos

| Riesgo | Mitigación |
|---|---|
| Migraciones con constraints duplicados | Normalizar nombres CHECK antes del Lote A; revisar `autogenerate` |
| Divergencia `stock_balance` vs reservas | Pruebas de concurrencia y regla de conciliación |
| UUID centinela sin FK | Columnas `*_ref_id` nullable + transición gradual |
| Alcance RBAC incompleto | Añadir aserciones de unidad/almacén en cada endpoint |
| Paginación ausente | Imponer límites y filtros desde el Lote A |
| Datos reales no autorizados | Semilla sintética y revisión de diff |
| IA instruyendo movimientos | Arquitectura de recomendación sólo lectura |
| Falta de SDK de CONTPAQi | Modo de mapeo y staging sin escritura |

---

## 8. Evidencia y documentación por lote

Cada lote debe generar o actualizar:

- `docs/WMS_LOTE_<X>_RESULTADOS.md`;
- migración con identificador explícito;
- pruebas backend/frontend;
- contratos API en el cliente tipado;
- pantallas o componentes nuevos;
- registro de decisiones y desviaciones.

---

# Apéndice A — Instrucción detallada para OpenCode: Lote A

> Copiar íntegramente esta sección como prompt para la sesión que ejecutará el Lote A. Está limitada exclusivamente a catálogos, ubicaciones y búsquedas.

---

## Prompt — Lote A: catálogos, ubicaciones y búsquedas

Trabaja en `E:\ERP_MINERO`. Antes de empezar, lee `AGENTS.md`, `docs/ARQUITECTURA.md`, `docs/MODELO_DATOS.md`, `docs/FLUJO_REQUISICIONES.md` y los seis documentos `docs/WMS_*.md`. Verifica que `git status --short` esté limpio; si hay cambios del usuario, detente y repórtalos. **No modifiques CONTPAQi, GMAO, firewall, puertos, `.env`, bases ajenas ni código fuera del alcance del Lote A. No hagas push.**

### A.1 Migración

Crea una migración Alembic aditiva con revisión `a1b2c3d4e5f6` y padre `f4a7c1e2b3d6`, archivo `backend/migrations/versions/a1b2c3d4e5f6_lote_a_catalogo_ubicaciones.py`.

Debe crear, siguiendo `docs/WMS_MODELO_DATOS.md` §3:

- `mdm.item_family`
- `mdm.item_uom_conversion`
- `mdm.item_cross_reference`
- `mdm.item_supplier`
- `mdm.storage_location`
- `mdm.location_restriction`
- `mdm.lot`
- `mdm.serial`
- vistas `mdm.v_item_search`, `mdm.v_location_occupancy` e `inv.v_stock_by_location`.

Añadir a `mdm.item` columnas nullable: `family_id`, `manufacturer`, `manufacturer_part_no`, `barcode`, `image_path`, `image_sha256`, `weight_kg`, `volume_m3`, `storage_temperature_min`, `storage_temperature_max`, `is_consumable`, `is_returnable`, `is_tool`, `default_supplier_id`.

Añadir a `inv.stock_balance`, `inv.stock_reservation` e `inv.stock_movement` columnas nullable `lot_ref_id` y `location_ref_id` con FK a `mdm.lot` y `mdm.storage_location`, sin eliminar las columnas `lot_id`/`location_id` actuales ni los valores centinela. Agregar CHECK de coherencia sólo si no bloquea filas existentes.

Añadir índices para búsqueda: texto de artículo, código de ubicación, `qr_token`, `expiry_date`, `warehouse_id + location_type`.

La migración no debe contener `DROP`, `TRUNCATE`, `DELETE`, `ALTER COLUMN ... DROP` ni `downgrade` destructivo. El `downgrade` debe lanzar un error explícito indicando que no se usa sobre datos reales.

Antes de la migración, corrige cualquier nombre de CHECK con doble prefijo `ck_<tabla>_ck_<tabla>_...` detectado en Fase 4 usando una migración separada `a0b1c2d3e4f5_normaliza_checks.py`, también aditiva en el sentido de que no elimina datos; si la corrección exige recrear constraints, hazlo sólo en una base vacía y documenta el riesgo. Si no es seguro, no la ejecutes y reporta el bloqueo.

### A.2 Modelos y esquemas

- Actualiza `backend/app/modules/master_data/models.py` con los nuevos modelos SQLAlchemy 2 (`Mapped[...]`, `mapped_column`). Usa `NUMERIC(18,6)` para cantidades y `NUMERIC(18,4)` para costos. Mantén FK `ondelete="RESTRICT"`.
- Crea `backend/app/modules/master_data/schemas.py` con modelos Pydantic v2 de entrada/salida. Prohíbe ID manual en creación; el servidor asigna UUID.
- No importes FastAPI en modelos de dominio.
- Registra los modelos nuevos donde Alembic y la semilla los cargan.

### A.3 Servicios y reglas

Implementa servicios en `master_data` (o un subpaquete `warehousing` si lo justificas, sin tocar otros módulos):

- Alta/baja lógica de familia, ubicación, lote y serie.
- Conversión UOM con `factor > 0` y vigencia.
- Equivalencia autorizada: si `authorised=true`, exige `approved_by` válido; si no, se devuelve como candidato, nunca como sustitución.
- QR único, opaco y sin credenciales.
- Restricciones de capacidad/temperatura/mezcla al consultar ubicación sugerida.
- Búsqueda con filtros `q`, `family_id`, `supplier_id`, `uom_id`, `lot_tracked`, `serial_tracked`, `warehouse_id`, `location_id`, `is_active`, `page`, `page_size`. Límite máximo `page_size=100`.
- Toda consulta de stock por ubicación respeta alcance por unidad minera/almacén del actor. Usa las funciones de `IdentityService`.

No cambies el comportamiento de `InventoryService.reserve`, `issue` ni `PurchasingService.receive`. Si necesitas un dato nuevo, expón una función de lectura, no una escritura.

### A.4 API

Agrega routers versionados bajo `/api/v1`, con `require_permission` y alias en español:

- `GET/POST /api/v1/catalog/item-families`
- `GET /api/v1/catalog/items/search`
- `GET /api/v1/catalog/items/{id}`
- `PATCH /api/v1/catalog/items/{id}`
- `POST /api/v1/catalog/items/{id}/uom-conversions`
- `GET/POST /api/v1/catalog/items/{id}/equivalences`
- `POST /api/v1/catalog/items/{id}/suppliers`
- `GET/POST /api/v1/warehouses/{id}/locations`
- `GET /api/v1/locations/{id}/qr`
- `GET /api/v1/locations/{id}/stock`
- `GET/POST /api/v1/lots`
- `GET/POST /api/v1/serials`

Permisos nuevos: `catalog.view`, `catalog.manage`, `warehouse.location.view`, `warehouse.location.manage`, `warehouse.stock.view`. Asignarlos en `constants.py` a ADMIN; catálogo en lectura a SOLICITANTE/COMPRADOR; ubicaciones y stock a ALMACENISTA/ALMACÉN. Actualizar pruebas de RBAC que verifiquen listas de permisos.

Todas las respuestas de lista llevan `page`, `page_size`, `total` e `items`. Ningún endpoint devuelve secretos ni rutas absolutas del servidor.

### A.5 Semilla sintética

Extiende `backend/app/db/seed.py` de forma idempotente con:

- 3 familias (`Consumibles`, `Repuestos`, `Herramientas`);
- conversiones de ejemplo, por ejemplo CJA→PIEZA con factor 20;
- 2 equivalencias: una autorizada y una no autorizada;
- 4 ubicaciones por almacén demo: recepción, cuarentena, despacho y una posición de pasillo;
- 2 lotes con caducidad futura y 2 series;
- un proveedor preferido por artículo demo.

Usa correos `example.invalid` y códigos claramente ficticios. No importes archivos de CONTPAQi ni datos reales. La contraseña demo continúa viniendo de `DEMO_PASSWORD`.

### A.6 Frontend

- Añade métodos tipados en `frontend/src/api/client.ts` y tipos en `frontend/src/api/types.ts`.
- Crea `frontend/src/features/warehousing/Catalog.tsx` y `Locations.tsx`.
- Búsqueda con filtros, tabla con paginación y estados vacíos accionables.
- Alta de ubicación/familia con formularios controlados; **no uses `window.prompt`**.
- Menú gated por permisos en `Layout.tsx`/`permissions.ts`.
- UI en español, responsive y sin `fetch` directo en componentes.

### A.7 Pruebas

Backend:

- migración `empty → head` y verificación de tablas/vistas;
- UNIQUE de `qr_token` y de código por almacén;
- `factor > 0`;
- equivalencia sin aprobador no se marca autorizada;
- búsqueda con paginación y filtros;
- acceso denegado a ubicaciones de otra unidad minera;
- semilla idempotente (ejecutar dos veces sin duplicados);
- regresión: 63 pruebas existentes siguen pasando.

Frontend:

- cliente API para los nuevos endpoints;
- render de búsqueda y paginación;
- menú oculto sin permiso.

Comandos:

```powershell
cd E:\ERP_MINERO\backend
python -m pytest -q
python -m ruff check .
python -m mypy app
python -m alembic current

cd E:\ERP_MINERO\frontend
npm.cmd run test -- --run
npm.cmd run build

cd E:\ERP_MINERO
python scripts\verificar_portal.py
```

### A.8 Documentación y cierre

Crea `docs/WMS_LOTE_A_RESULTADOS.md` con:

- revisión de migración;
- tablas y vistas creadas;
- endpoints nuevos;
- permisos nuevos;
- resultados de pruebas;
- decisiones tomadas;
- limitaciones (sin movimientos, sin móvil, sin IA);
- siguiente paso: Lote B.

Haz un commit local en español, por ejemplo:

```text
Agrega catalogo WMS, ubicaciones con QR y busqueda paginada
```

No hagas push. No abras puertos ni modifiques infraestructura.

### A.9 Prohibiciones del Lote A

- No implementar entradas, salidas, traspasos, conteos, herramientas, costos, móvil ni IA.
- No modificar `inv.stock_movement` en escritura.
- No eliminar columnas ni datos existentes.
- No conectar a CONTPAQi ni GMAO.
- No usar `0.0.0.0`.
- No guardar secretos ni certificados.
- No declarar producción ni piloto LAN activo.
