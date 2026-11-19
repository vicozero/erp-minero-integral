# WMS — Matriz de integración con CONTPAQi Comercial Premium 11.5.1

**Fecha:** 2026-11-18

**Estado:** DISEÑO DE INTEGRACIÓN. No se implementó conexión ni escritura real.
**Regla crítica:** CONTPAQi es el sistema oficial de Almacén y Compras. Está **prohibido** conectarse a su base de datos. El ERP sólo prepara mapeos, staging, conciliación y eventos.

---

## 1. Principios de integración

| ID | Principio |
|---|---|
| CI-01 | Sin acceso directo a tablas de CONTPAQi. |
| CI-02 | Sólo archivos controlados o API oficial autorizada por el proveedor. |
| CI-03 | Toda carga pasa por `intg.integration_batch` → `intg.integration_staging` → validación → destino. |
| CI-04 | Cada archivo se registra por nombre, SHA-256, tamaño, usuario y resultado. |
| CI-05 | Los identificadores externos se guardan como referencia, nunca como llave primaria interna. |
| CI-06 | No se publican asientos ni movimientos a CONTPAQi sin aprobación. |
| CI-07 | Reintentos seguros con idempotencia; nunca reintentar errores de validación. |
| CI-08 | Las diferencias se concilian y se aprueban; nunca se autoajusta el sistema oficial. |
| CI-09 | Los datos del piloto son exclusivamente sintéticos. |
| CI-10 | Sin SDK, compatibilidad o permisos verificados, la integración permanece en modo diseño. |

---

## 2. Estado actual de `intg`

Tablas existentes en head `f4a7c1e2b3d6`:

| Tabla | Uso actual | Ampliación WMS |
|---|---|---|
| `intg.external_system` | Catálogo de sistemas, con `official_inventory` | Registrar CONTPAQi 11.5.1 como oficial y GMAO como externo |
| `intg.outbox_event` | Eventos transaccionales | Propuestas de sincronización y reintentos |
| `intg.inbox_event` | Idempotencia de entrada | Confirmaciones y errores devueltos |

**No existen aún:** `external_mapping`, `integration_batch`, `integration_staging`, `external_document_ref`, `reconciliation_snapshot(_line)`. Están descritas en `MODELO_DATOS.md:615+` y se proponen para el Lote F/H según corresponda.

---

## 3. Mapa de correspondencias

### 3.1 Artículos

| ERP interno | CONTPAQi | Regla |
|---|---|---|
| `mdm.item.code` | Código de artículo | Único por compañía; normalizar mayúsculas/espacios |
| `mdm.item.description` | Descripción | No sobreescribir descripción oficial sin aprobación |
| `mdm.item_uom_conversion` | Unidades de la mina | Factor de conversión explícito; nunca asumir 1:1 |
| `mdm.item_cross_reference` | Claves alternas del proveedor | `reference_type='CONTPAQI'` y `authorised` |
| `mdm.lot` / `mdm.serial` | Lotes/series si el módulo los soporta | Validar soporte real en 11.5.1 |
| `mdm.item.standard_cost` | Costo estándar/costo de última compra | Sólo referencia hasta aprobación contable |

**Duplicados:** candidato cuando coinciden código normalizado + fabricante + número de parte, o cuando el hash de atributos es igual. Se registra en `wms.duplicate_candidate`; requiere revisión humana.

### 3.2 Almacenes y ubicaciones

| ERP interno | CONTPAQi | Regla |
|---|---|---|
| `org.warehouse.code` | Almacén | Un almacén ERP equivale a un almacén externo autorizado |
| `mdm.storage_location` | Ubicación interna / pasillo | Si CONTPAQi no soporta esa granularidad, se mantiene sólo en el ERP |
| `org.mining_unit` | Unidad minera / centro | Aislamiento obligatorio |

### 3.3 Documentos

| ERP interno | CONTPAQi | Regla |
|---|---|---|
| `doc.document_registry.full_number` | Folio del documento | Relación 1:1 mediante `external_document_ref` |
| `req.requisition` | Requisición interna | No se envía a CONTPAQi como movimiento oficial |
| `pur.purchase_order` | Orden de compra | Relación por folio y proveedor |
| `pur.goods_receipt` | Entrada/almacén | Sólo exportación propuesta hasta autorización |
| `inv.stock_movement` | Movimiento de inventario | Conciliación, no escritura automática |
| `cost.cost_posting` | Asiento contable | Nunca se publica sin aprobación |

### 3.4 Proveedores y unidades

| ERP interno | CONTPAQi | Regla |
|---|---|---|
| `mdm.supplier.code` | Código de proveedor | Mapeo explícito; no inferir por nombre |
| `mdm.uom.code` | Unidad de medida | Tabla de equivalencia con factor |
| `org.employee.employee_code` | Empleado/usuario | Sólo si se autoriza uso de datos de personas |

---

## 4. Modelo de datos de integración propuesto

### 4.1 `intg.external_mapping`

- `external_system_id` → `intg.external_system`
- `internal_entity_type` (por ejemplo `Item`, `Warehouse`, `Uom`)
- `internal_entity_id UUID`
- `external_key TEXT`
- `external_payload_hash TEXT`
- `status` ∈ `ACTIVE`, `PENDING_REVIEW`, `DUPLICATE`, `INACTIVE`
- `approved_by`, `approved_at`
- UNIQUE `(external_system_id, internal_entity_type, external_key)`
- UNIQUE `(external_system_id, internal_entity_type, internal_entity_id)`

### 4.2 `intg.integration_batch`

- `external_system_id`
- `file_name`, `sha256`, `size_bytes`
- `source` ∈ `MANUAL_FILE`, `AUTHORIZED_API`, `EXPORT`
- `uploaded_by`, `uploaded_at`
- `status` ∈ `RECEIVED`, `VALIDATING`, `VALID`, `REJECTED`, `APPLIED`, `FAILED`
- `row_count`, `accepted_count`, `rejected_count`
- `error_summary JSONB`

### 4.3 `intg.integration_staging`

- `batch_id`
- `row_no`
- `payload JSONB`
- `row_hash`
- `validation_status`
- `error_code`, `error_detail`
- `target_entity_type`, `target_entity_id`
- `processed_at`
- UNIQUE `(batch_id, row_no)`

### 4.4 `intg.external_document_ref`

- `document_registry_id`
- `external_system_id`
- `external_document_type`
- `external_document_no`
- `status`
- `last_attempt_at`, `attempts`
- `external_error`
- UNIQUE `(external_system_id, external_document_type, external_document_no)`

### 4.5 `intg.reconciliation_snapshot(_line)`

- Sistema, fecha, almacén, artículo, lote, ubicación y costo.
- Línea con existencia operativa, existencia oficial, diferencia y resolución.
- Nunca modifica la existencia oficial.

---

## 5. Flujo de importación controlada

```text
Archivo autorizado / API oficial
        │
        ▼
intg.integration_batch  (nombre, hash, tamaño, usuario)
        │
        ▼
intg.integration_staging (fila, payload, validación)
        │
        ├─ inválida → error por fila, sin escribir destino
        │
        ▼
Reglas de mapeo y duplicados
        │
        ▼
Tablas destino (mdm/org/cost) en transacción
        │
        ▼
aud.audit_log + intg.outbox_event
        │
        ▼
Resultado del batch y notificación
```

Reglas:

- Un archivo duplicado por SHA-256 se rechaza o se marca como reproceso autorizado.
- Una fila inválida no bloquea a las demás; se registra y se reporta.
- La validación es determinista y repetible.
- La aplicación de cambios es idempotente por `row_hash` y `external_key`.

---

## 6. Flujo de exportación propuesta

```text
Evento de negocio (outbox)
        │
        ▼
Propuesta de sincronización  (no movimiento oficial)
        │
        ▼
Revisión/ aprobación humana
        │
        ▼
Archivo controlado o llamada API autorizada
        │
        ▼
Confirmación → intg.inbox_event
        │
        ▼
external_document_ref + auditoría
```

Mientras no exista SDK/API verificada:

- No se envían movimientos reales.
- Se generan propuestas en forma de borrador/exportación controlada.
- El usuario responsable decide si se carga manualmente en CONTPAQi.

---

## 7. Reintentos y errores

| Error | Acción |
|---|---|
| Archivo corrupto / hash distinto | Rechazar batch; no reprocesar |
| Fila inválida | Marcas `REJECTED` con código y detalle |
| Clave externa duplicada | Marcar `DUPLICATE`; no crear entidad |
| Conflicto de mapeo | `PENDING_REVIEW`; requiere humano |
| Timeout de API autorizada | Reintento con backoff exponencial acotado |
| Error de validación de negocio | Sin reintento; corregir origen |
| Confirmación duplicada | `inbox_event` con `event_id` único; ignorar |
| Agotamiento de intentos | Dead-letter y alerta; nunca descartar silenciosamente |

Política: máximo 5 intentos, backoff 1/2/4/8/16 minutos, registrar cada intento. Sólo reintentar fallos transitorios.

---

## 8. Detección de duplicados

Criterios combinados:

1. Mismo SHA-256 de archivo.
2. Misma clave externa para el mismo sistema y tipo de entidad.
3. Misma clave normalizada: código + fabricante + número de parte.
4. Similitud semántica alta en descripción (sugerencia IA; nunca aplicación automática).

Acción:

- Marcar `DUPLICATE` o `PENDING_REVIEW`.
- Conservar ambas filas en staging.
- No fusionar artículos sin aprobación.
- Registrar quién resolvió y por qué.

---

## 9. Conciliación de existencias y costos

```text
Snapshot operativo ERP  ─┐
                         ├─ Comparación → diferencias por artículo/lote/ubicación/costo
Snapshot oficial CONTPAQi┘
```

Reglas:

- El snapshot operativo se toma de `inv.stock_balance` y `inv.stock_movement`.
- El oficial se obtiene por archivo/API autorizada; nunca por conexión directa.
- Las diferencias se clasifican: cantidad, costo, ubicación, lote, documento faltante.
- Cada diferencia requiere investigación, motivo y aprobación.
- El ERP puede proponer un ajuste operativo; CONTPAQi conserva su propio proceso oficial.
- No se declara conciliación exitosa si quedan diferencias sin resolver.

---

## 10. Fases de activación

| Fase | Alcance | Estado |
|---|---|---|
| 0 | Sin integración; sólo diseño y mapeo documental | Actual |
| 1 | Catálogos de mapeo y batch/staging con archivos sintéticos | Pendiente Lote A/F |
| 2 | Importación controlada de maestros sintéticos | Pendiente |
| 3 | Exportación de propuestas y confirmaciones simuladas | Pendiente |
| 4 | Integración real con SDK/API verificada y permisos formales | Bloqueada |
| 5 | Decisión formal sobre migración de inventario oficial | Fuera de alcance |

---

## 11. Requisitos para habilitar integración real

1. Verificar versión exacta 11.5.1 y compatibilidad del SDK/API.
2. Obtener autorización por escrito del proveedor/área de sistemas.
3. Definir canal: archivo controlado o API oficial.
4. Definir credenciales gestionadas fuera del repositorio.
5. Validar permisos por compañía, almacén y documento.
6. Definir formatos, códigos y reglas de normalización.
7. Ejecutar prueba con datos sintéticos en entorno aislado.
8. Probar reintentos, duplicados y reversión.
9. Obtener aprobación de Finanzas para costos/asientos.
10. Declarar formalmente si CONTPAQi deja de ser oficial; mientras tanto, no.

---

## 12. Riesgos

| Riesgo | Impacto | Mitigación |
|---|---|---|
| Conexión directa no autorizada | Crítico | Prohibición técnica y de proceso; staging obligatorio |
| Escritura contable prematura | Crítico | Sólo propuestas hasta aprobación |
| Códigos UOM inconsistentes | Alto | Tabla de equivalencia con factor |
| Duplicados de artículos | Alto | Detección y revisión humana |
| Pérdida de eventos | Medio | Outbox + reintentos + dead-letter |
| Datos reales en piloto | Crítico | Sólo sintéticos; revisión de diff |
| Cambio de versión de CONTPAQi | Medio | Registro de versión y pruebas de compatibilidad |
| Confusión de inventario oficial | Crítico | Documentación y banderas `official_inventory` |

---

## 13. Criterios de aceptación

- No existe código que apunte a la base de CONTPAQi.
- Toda carga queda registrada en batch/staging con hash y usuario.
- Los mapeos son reversibles y auditables.
- Los duplicados nunca se fusionan automáticamente.
- Los reintentos no duplican efectos.
- Las propuestas requieren aprobación humana.
- Las conciliaciones dejan rastro y no modifican el sistema oficial.
- La integración real permanece desactivada hasta cumplir los requisitos de la sección 11.
