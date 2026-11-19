# ERP MINERO INTEGRAL — Matriz de cobertura funcional MRO + WMS + Compras + IA

> Fase A — auditoría de cobertura funcional y modelo de datos.
>
> Fecha: 2026-11-19
>
> Línea base: HEAD real `4a493b8` (`Agrega contratos, permisos y bandera del Lote B WMS`).
>
> Alcance: **solo documentación**. No se modificó código, no se aplicaron migraciones, no se hizo push ni despliegue.
>
> Documentos relacionados: `ERP_MRO_WMS_PLAN_MAESTRO.md`, `ERP_MRO_WMS_DEPENDENCIAS.md`.

---

## 0. Metodología y leyenda

La matriz se construyó con inspección estática de `backend/app/**`, `backend/migrations/versions/**`, `frontend/src/**`, `scripts/**` y la documentación del repositorio. **No se ejecutaron** migraciones, pruebas ni servidores durante Fase A.

| Estado | Significado |
|---|---|
| **IMPLEMENTADO** | Existe código ejecutable, migración aplicada en la cadena `head` y, cuando aplica, prueba automatizada. |
| **PARCIAL** | Existe una parte de la capacidad (tabla, campo o endpoint), pero falta regla de negocio, aprobación, UI o integración. |
| **DISEÑO** | Existe documentación de diseño y/o contratos, pero no hay implementación ejecutable. |
| **AUSENTE** | No existe entidad, servicio ni documento que la cubra. |
| **DUPLICADO** | La capacidad se resuelve en más de un lugar con riesgo de divergencia; ver sección 4. |

> Regla de lectura: **PARCIAL no equivale a terminado**. Un módulo solo se declara cubierto cuando todas sus capacidades críticas están IMPLEMENTADO y cuentan con prueba PostgreSQL real cuando hay transacciones.

---

## 1. Línea base técnica verificada

| Capa | Estado observado |
|---|---|
| Módulos backend con modelos | 12 (`identity`, `organization`, `master_data`, `documentation`, `requisitions`, `workflow`, `inventory`, `purchasing`, `maintenance`, `costing`, `integrations`, `audit`). |
| Tablas SQLAlchemy | 49, en los esquemas `seg, org, mdm, doc, req, wfl, inv, pur, mnt, cost, intg, aud`. |
| Operaciones HTTP | 55: `health` 3, `auth` 6, `admin` 13, `catalogs` 1, `requisitions` 11, `inventory` 6, `purchases` 6, `wms` 9, `audit` 1. |
| Alembic | Cadena `0001_initial_schema` → `d147e7ec92fb` → `f3a9c1d7b2e4` → `f4a7c1e2b3d6` → `a1b2c3d4e5f6` (head). No existe `b7c8d9e0f1a2`. |
| Feature flag | `WMS_LOTE_B_ENABLED=False` (`backend/app/core/config.py`). No hay rutas `/api/v1/wms/movements`. |
| Frontend | 13 pantallas en 11 features (`admin`, `approvals`, `audit`, `auth`, `catalog`, `dashboard`, `history`, `inventory`, `purchases`, `requisitions`, `wms`). Cliente API manual tipado (`src/api/client.ts`), sin `fetch` en componentes. |
| Pruebas | 77 backend, 25 frontend; smoke de portal con datos sintéticos. Base de pruebas PostgreSQL real `erp_minero_test`, Alembic `head`. |
| Portal | Backend `127.0.0.1:8000`, proxy `127.0.0.1:8080`, Vite dev `127.0.0.1:5173`; `PORTAL_ALLOW_LAN=false`. |
| Roles | 10 códigos (`ADMIN`, `SOLICITANTE`, `JEFE_DEPARTAMENTO`, `APROBADOR`, `ALMACENISTA`, `ALMACEN`, `COMPRADOR`, `COMPRAS`, `GERENCIA`, `AUDITOR`) con aliases heredados. |

---

## 2. Matriz de los nueve módulos

### Módulo 1 — Catálogo maestro MRO

| Capacidad requerida | Estado | Evidencia / brecha real |
|---|---|---|
| Código interno único | **PARCIAL** | `mdm.item.code` es único por compañía (`uq_item_company_code`); no distingue código interno de OEM/fabricante ni tiene regla de inmutabilidad. |
| Número de parte OEM y de fabricante | **PARCIAL** | `Item.manufacturer_part_no` y `ItemCrossReference.reference_type IN ('MANUFACTURER',…)` existen; falta campo OEM separado y normalización. |
| Marca y fabricante | **PARCIAL** | `Item.manufacturer` existe; no hay entidad `brand` ni separación marca/fabricante. |
| Familias y subfamilias | **PARCIAL** | `mdm.item_family.parent_id` permite jerarquía; no hay validación de ciclos ni profundidad, ni vista de subfamilia. |
| Descripción técnica normalizada | **AUSENTE** | Solo `Item.description` libre (255). |
| Unidades de medida | **IMPLEMENTADO** | `mdm.uom`, `Item.uom_id`, `purchase_uom_id`, `mdm.item_uom_conversion` con `factor > 0` y vigencia. |
| Equivalencias autorizadas y no autorizadas | **PARCIAL** | `mdm.item_cross_reference` ya tiene `authorised`, `approved_by` obligatorio si autoriza, `valid_from/valid_to`. Falta UI, regla de uso en movimientos y bloqueo de sustitución automática. |
| Compatibilidad por modelo y equipo | **AUSENTE** | Existe `mnt.equipment`, pero no hay tabla de compatibilidad ítem↔modelo/equipo. |
| Fotografías, fichas técnicas y manuales | **PARCIAL** | `image_path`/`image_sha256` y `GET|POST /wms/items/{id}/photo` (una sola imagen). Sin fichas ni manuales. |
| Proveedores asociados | **IMPLEMENTADO** | `mdm.item_supplier` con `lead_time_days`, `min_order_qty`, `preferred`, `last_unit_cost`, `currency`. |
| Histórico de cambios del catálogo | **PARCIAL** | `AuditMixin` guarda auditoría de fila, pero no hay tabla append-only de versiones de catálogo consultable. |
| Artículos duplicados sugeridos | **AUSENTE** | Sin regla ni endpoint de sugerencia. |
| Materiales obsoletos y sustitutos aprobados | **AUSENTE** | Sin `obsolete`, `superseded_by` ni flujo de aprobación. |

**Conclusión:** PARCIAL. La base del catálogo es amplia (Lote A), pero la semántica MRO de compatibilidad, obsolescencia, duplicados y normalización no existe. Fase destino: **C**.

---

### Módulo 2 — Inventario inteligente

| Capacidad requerida | Estado | Evidencia / brecha real |
|---|---|---|
| Existencias físicas y disponibles | **IMPLEMENTADO** | `inv.stock_balance.on_hand_qty`, `reserved_qty`, CHECK `on_hand >= reserved`; disponible = diferencia. |
| Cantidades reservadas | **IMPLEMENTADO** | `inv.stock_reservation`, endpoints `POST /inventory/reservations`, `GET /inventory/reservations`, `/expire`. |
| Existencias por almacén y ubicación | **PARCIAL** | `stock_balance` tiene `warehouse_id` y `location_ref_id`, pero `lot_id/location_id` siguen siendo UUID centinela; no hay detalle por lote/serie/estado/ubicación (B.1). |
| Máximos, mínimos, stock de seguridad, punto de reorden | **PARCIAL** | Campos en `mdm.item` (`reorder_point`, `safety_stock`, `max_stock`); no hay cálculo ni alerta que los consuma. |
| Criticidad por equipo | **PARCIAL** | `mnt.equipment.criticality` existe; no hay cruce con saldos ni consumo. |
| Clasificación ABC y XYZ | **AUSENTE** | Sin cálculo ni persistencia. |
| Cobertura estimada | **AUSENTE** | Sin cálculo de días de cobertura. |
| Consumo histórico | **PARCIAL** | `inv.stock_movement` registra hechos; falta agregación por período, equipo y artículo. |
| Tiempos de reposición | **PARCIAL** | `mdm.item_supplier.lead_time_days` existe por proveedor; no se usa en recomendaciones. |
| Recomendaciones de abastecimiento | **AUSENTE** | Sin motor determinista. |
| Alertas de desabasto | **AUSENTE** | Sin endpoint ni regla. |
| Control de inventario inmovilizado | **AUSENTE** | Sin indicador de sin movimiento. |
| Separación calculado vs predicción | **AUSENTE** | No hay contrato de respuesta con `computed_at`, `source`, `period` ni etiqueta de predicción. |

**Conclusión:** PARCIAL en datos base, AUSENTE en inteligencia. Fase destino: **D**, condicionada a B completo.

---

### Módulo 3 — WMS avanzado

| Capacidad requerida | Estado | Evidencia / brecha real |
|---|---|---|
| Catálogo y ubicaciones (Lote A) | **IMPLEMENTADO** | 9 endpoints `/wms/*`: familias, búsqueda/detalle/foto de artículo, alta y detalle de ubicación. |
| QR escaneable | **PARCIAL** | `storage_location.qr_token` como texto; sin generación gráfica, impresión ni lectura. |
| Lotes y series | **IMPLEMENTADO (catálogo)** | `mdm.lot`, `mdm.serial` con estados y restricciones; sin consumo transaccional en movimientos WMS. |
| Entradas y recepciones enriquecidas | **DISEÑO** | `WMS_LOTE_B_DISENO.md` §3.2; B.3 no implementado. Existe solo recepción heredada desde OC (`purchasing`). |
| Salidas por requisición y OT | **PARCIAL / DISEÑO** | `POST /inventory/issues` heredado funciona por requisición; salida enriquecida con `work_order_no`, lote/serie y doble barrera es B.4 (diseño). |
| Devoluciones y cuarentena | **DISEÑO** | §4 del diseño; B.5 pendiente. `mdm.lot.status` incluye `QUARANTINE`, pero no hay movimiento de cuarentena. |
| Kardex | **PARCIAL** | `GET /inventory/kardex` heredado; vista `inv.v_kardex` y filtros por documento/equipo/OT son B.7 (diseño). |
| Reversos e inmutabilidad | **DISEÑO** | Campo `reversal_of_id` existe, pero sin trigger, ni restricción de reverso duplicado, ni API. B.1/B.6. |
| Traspasos entre ubicaciones | **AUSENTE** | No hay tipo de movimiento ni modelo de tarea para transferencia interna. |
| Transferencias entre almacenes y material en tránsito | **AUSENTE / DISEÑO** | Documentado para Lote C; sin implementación. |
| Recepción parcial | **PARCIAL** | `pur.goods_receipt` / `goods_receipt_line` y OC `PARTIALLY_RECEIVED` existen en compras; no en WMS independiente. |
| Conciliación, inventarios físicos, conteos cíclicos, ajustes autorizados | **AUSENTE / DISEÑO** | Solo diseño B.1/B.7 y Lote C. `MOVEMENT_TYPES` no incluye `COUNT`/`PHYSICAL_COUNT`. |

**Conclusión:** PARCIAL (Lote A + capa heredada). El WMS transaccional **no está terminado**; solo B.0. Fase destino: **B** (B.1–B.10) y luego Lote C.

---

### Módulo 4 — Requisiciones

| Capacidad requerida | Estado | Evidencia / brecha real |
|---|---|---|
| Captura guiada | **PARCIAL** | UI `Requisitions.tsx` + `ItemPicker.tsx`; no hay asistente por tipo de artículo, equipo u OT. |
| Múltiples partidas | **IMPLEMENTADO** | `req.requisition_line` con `line_no` ordenado y `uq_requisition_line`. |
| Búsqueda MRO | **PARCIAL** | `GET /wms/items/search` existe; no hay filtro por compatibilidad/equipo ni sinónimos. |
| Prioridades | **IMPLEMENTADO** | `Requisition.priority IN ('LOW','NORMAL','HIGH','URGENT')`. |
| Equipo y OT | **PARCIAL** | `equipment_id` y `work_order_no` (texto) en cabecera; sin entidad OT. |
| Centro de costo | **IMPLEMENTADO** | `cost_center_id` obligatorio en cabecera. |
| Autorización individual por partida | **IMPLEMENTADO** | `authorised_qty` por línea y decisiones en `wfl.approval_step` / `approval_decision`; 11 endpoints. |
| Autorizado, reservado, comprado, recibido, surtido | **PARCIAL** | `authorised_qty` y `cancelled_qty` en línea; `reserved`, `purchased`, `received`, `delivered` se derivan de tablas detalle pero no se exponen como proyección única. |
| Historial | **IMPLEMENTADO** | `GET /requisitions/{id}/history`; `document_event`, `audit_log`. |
| Adjuntos | **IMPLEMENTADO** | `req.requisition_attachment` append-only, SHA-256 y endpoints de lista/descarga. |
| Seguimiento | **PARCIAL** | Estados y fechas en cabecera; sin línea de tiempo por hito ni notificaciones. |
| Reportes imprimibles | **AUSENTE** | Sin plantilla ni endpoint de impresión/PDF. |

**Conclusión:** PARCIAL — núcleo sólido y compatible. Fase destino: **C** para búsqueda MRO, **B.4** para cantidades surtidas, **F** para OT. Mantener los 11 endpoints actuales intactos.

---

### Módulo 5 — Compras

| Capacidad requerida | Estado | Evidencia / brecha real |
|---|---|---|
| OC desde requisición autorizada | **IMPLEMENTADO** | `pur.purchase_order`, `purchase_order_line`; endpoint `POST /purchases`; prueba dedicada. |
| Autorizaciones por importe | **PARCIAL** | `POST /purchases/{id}/approve` con `purchase.order.approve`; sin umbrales por importe configurables. |
| Entregas parciales y recepciones | **IMPLEMENTADO** | `pur.goods_receipt(_line)`, estados `PARTIALLY_RECEIVED`, `POST /purchases/{id}/receive`, `CostLayer` por línea. |
| Devoluciones a proveedor | **AUSENTE** | Sin tipo de movimiento ni documento de devolución a proveedor. |
| RFQ y comparativos de proveedores | **AUSENTE** | Sin `pur.rfq` ni `pur.quote`. |
| Precios, plazos y selección justificada | **PARCIAL** | `mdm.item_supplier` tiene precio/lead time; no hay comparativo ni motivo de adjudicación. |
| Evaluación de proveedores | **AUSENTE** | Sin indicadores de cumplimiento. |
| Triple match OC–recepción–factura | **AUSENTE** | No existe factura de compra ni `match_result`. |
| CFDI/XML por integración autorizada | **AUSENTE** | Sin staging de documentos; prohibida conexión directa a CONTPAQi. |
| Gestión de compromisos de gasto | **AUSENTE** | Sin proyección de gasto comprometido. |
| Aislamiento CONTPAQi | **PARCIAL** | `intg.external_system`, `outbox_event`, `inbox_event` existen; sin adaptador ni batch de importación. |

**Conclusión:** PARCIAL. **No declarar compras listas para producción** sin triple match y conciliación. Fase destino: **E**.

---

### Módulo 6 — Refacciones por OT

| Capacidad requerida | Estado | Evidencia / brecha real |
|---|---|---|
| Equipo | **IMPLEMENTADO** | `mnt.equipment` con `asset_tag`, `criticality`, `external_gmao_id`. |
| Asociación OT ↔ requisición | **PARCIAL** | `Requisition.work_order_no` como texto libre; sin entidad OT ni FK. |
| Refacciones planeadas / reservadas / entregadas / devueltas / consumidas | **AUSENTE** | No existen líneas de refacción por OT. |
| Costo por OT y por equipo | **AUSENTE** | `cost.cost_layer` existe para compras, sin imputación a OT/equipo. |
| Historial de materiales utilizados | **PARCIAL** | `inv.stock_movement` podrá tener snapshot de OT en B.4; hoy sin ese campo. |
| Compatibilidad con el equipo | **AUSENTE** | Sin tabla de compatibilidad. |
| Planeado vs real | **AUSENTE** | Sin planeado. |
| Preparación GMAO | **PARCIAL** | Solo `external_gmao_id`; sin `intg.gmao_sync_event` ni adaptador. |

**Conclusión:** AUSENTE salvo equipo y referencia textual. Fase destino: **F**, después de B.4 y de aprobar el modelo OT (D-10).

---

### Módulo 7 — Control de herramientas

| Capacidad requerida | Estado | Evidencia / brecha real |
|---|---|---|
| Catálogo de herramientas | **AUSENTE** | Solo banderas `Item.is_tool`, `is_returnable`, `is_consumable` sin entidad ni reglas. |
| Identificador individual y número de serie | **PARCIAL** | `mdm.serial` genérico; no está ligado a herramienta ni a responsable. |
| Código QR | **PARCIAL** | `storage_location.qr_token`; sin QR de herramienta. |
| Responsable, préstamo, resguardo, devolución | **AUSENTE** | Sin `mnt.tool_loan`. |
| Condición física, extravío, daño | **PARCIAL** | `mdm.serial.status` incluye `DAMAGED`, `LOST`, `RETIRED`; no es historial de herramienta. |
| Calibraciones y vencimientos | **AUSENTE** | Sin entidad de calibración. |
| Historial por trabajador, cuadrilla y OT | **AUSENTE** | Sin modelo de cuadrilla. |
| Separación retornables vs consumibles | **PARCIAL** | Banderas en `mdm.item` sinCHECK ni flujo que las respete. |

**Conclusión:** AUSENTE. Requiere decisión D-09 (modelo de herramienta) y D-10 (alcance OT). Fase destino: **F**.

---

### Módulo 8 — IA predictiva

| Capacidad requerida | Estado | Evidencia / brecha real |
|---|---|---|
| Pronóstico de consumo | **AUSENTE** | Sin código ni diseño de modelo. |
| Riesgo de desabasto | **AUSENTE** | Solo reglas normativas pendientes de Fase D. |
| Detección de consumo anormal | **AUSENTE** | Sin motor de reglas. |
| Sugerencias de máximos y mínimos | **AUSENTE** | Campos en `mdm.item`, sin sugerencias. |
| Detección de duplicados MRO | **AUSENTE** | Sin algoritmo. |
| Recomendación de reabastecimiento | **AUSENTE** | Sin motor. |
| Comportamiento por equipo | **AUSENTE** | Sin agregación por equipo. |
| Explicación de recomendaciones | **AUSENTE** | Sin contrato de explicación. |
| Principio "IA no autoriza / no mueve stock" | **IMPLEMENTADO como norma** | `AGENTS.md` y plan maestro §1; sin control técnico aún. |

**Conclusión:** AUSENTE. Solo principios normativos. No hay volumen histórico autorizado. Fase destino: **H**, con reglas deterministas primero y control técnico de no escritura en `inv`/`pur`.

---

### Módulo 9 — Dashboard ejecutivo

| Capacidad requerida | Estado | Evidencia / brecha real |
|---|---|---|
| Dashboard operativo | **IMPLEMENTADO** | `frontend/src/features/dashboard/Dashboard.tsx`; KPIs calculados desde APIs reales; panel “Indicadores no disponibles con la API actual”. Sin números inventados. |
| Paneles por rol (Gerencia, Almacén, Compras, Mantenimiento, Administración) | **PARCIAL** | Guards por permiso en `App.tsx`; un solo dashboard genérico, sin paneles diferenciados. |
| Inventario valorizado | **PARCIAL** | Existen `standard_cost` y `cost_layer`, sin endpoint valorizado. |
| Rotación, exactitud, sin movimiento, faltantes, nivel de servicio | **AUSENTE/A DISEÑO** | Definidos en Fase D; sin contrato de KPI. |
| Compras pendientes y entregas parciales | **PARCIAL** | Estado de OC disponible vía API; sin KPI agregado. |
| Consumo por equipo y costo por OT | **AUSENTE** | Depende de Fase F. |
| Presupuesto vs gasto | **AUSENTE** | Sin presupuesto. |
| Riesgo de desabasto y productividad de almacén | **AUSENTE** | Sin cálculo. |
| Fórmula, fuente, período y filtros por indicador | **AUSENTE** | No hay `DASHBOARD_KPIS.md` ni contrato con metadatos. |
| SIN DATOS cuando falte información | **PARCIAL** | Mensaje genérico en frontend; sin contrato backend `value|null, status`. |

**Conclusión:** PARCIAL. Existe la base visual, pero no el contrato de KPI exigido. Fase destino: **G**.

---

## 3. Resumen de cobertura

| Módulo | Capacidades IMPLEMENTADO | PARCIAL | DISEÑO | AUSENTE | Fase |
|---|---:|---:|---:|---:|---|
| 1. Catálogo MRO | 2 | 7 | 0 | 4 | C |
| 2. Inventario inteligente | 2 | 5 | 0 | 6 | D |
| 3. WMS avanzado | 2 | 4 | 4 | 4 | B + C |
| 4. Requisiciones | 6 | 5 | 0 | 1 | B/C/F |
| 5. Compras | 2 | 4 | 0 | 6 | E |
| 6. Refacciones por OT | 1 | 3 | 0 | 7 | F |
| 7. Herramientas | 0 | 4 | 0 | 7 | F |
| 8. IA predictiva | 1 (norma) | 0 | 0 | 8 | H |
| 9. Dashboard ejecutivo | 1 | 4 | 0 | 8 | G |

> Los conteos son por capacidad listada en la sección 2, no por tabla ni por archivo. No constituyen porcentaje de avance del proyecto.

---

## 4. Duplicidades y solapamientos detectados

Ninguna se corrige en Fase A. Se documentan para decidir su resolución en el lote que corresponda, **sin eliminar datos ni columnas existentes**.

| ID | Duplicidad | Evidencia | Riesgo | Resolución propuesta (no ejecutada) |
|---|---|---|---|---|
| DU-01 | `lot_id`/`location_id` (UUID centinela) conviven con `lot_ref_id`/`location_ref_id` en saldos, reservas y movimientos. | `inventory/models.py:28-40`, `:60-72`, `:96-121` | Dos lecturas del mismo scope; filtros que usen la columna equivocada devuelven vacío. | Mantener heredadas para compatibilidad; usar `*_ref_id` como dimensión canónica y `inv.stock_balance_detail` (B.1) como proyección. Nunca reutilizar el centinela. |
| DU-02 | `mdm.serial.current_location_id` vs `location_ref_id` del movimiento/saldo. | `master_data/models.py:238-240` | La ubicación “actual” de la serie puede divergir del kardex. | La ubicación de la serie debe ser derivada del último movimiento, no un valor independiente; decidir en B.4. |
| DU-03 | `document_no` en cabeceras vs `doc.document_registry.full_number`. | `requisitions/models.py:26-29`, `documentation/models.py:47+` | Dos folios visibles para un mismo documento. | `document_registry` es la autoridad de numeración; `document_no` queda como copia de compatibilidad y se valida en escritura. |
| DU-04 | `idempotency_key` repetido en reservas, movimientos y registros de documento. | `inventory/models.py:46,66,78,108` | Claves distintas para un mismo evento → doble emisión. | Clave canónica por intención física con prefijo por tipo; unicidad por tabla más correlación en `outbox`. Ver §7.1 del diseño B. |
| DU-05 | Permisos canónicos en inglés + aliases en español + nuevos permisos WMS B. | `shared/constants.py:10-151` | Una política escrita con alias distinto puede otorgar más de lo previsto; confusión al auditar. | `canonical_permission()` ya resuelve aliases; documentar que el catálogo canónico es la única autoridad y revisar `audit.view_all` (ver DU-06). |
| DU-06 | `audit.view_all` se comprueba en código pero **no está declarado** en `PERMISSIONS`. | `api/v1/routers/audit.py:30-31` vs `shared/constants.py:10-114` | Permiso fantasma: no se puede asignar desde permisos conocidos; comportamiento dependiente de ADMIN. | Declarar o eliminar la comprobación en su lote, con prueba RBAC. No hacerlo en Fase A. |
| DU-07 | Bitácora/historial duplicados en frontend: `features/audit/Audit.tsx` y `features/history/History.tsx` (varias tarjetas por pantalla). | `frontend/src/features/audit/`, `features/history/` | Fórmulas y filtros divergentes; mantenimiento duplicado. | Unificar en un componente compartido con contrato único en Fase G. |
| DU-08 | Cabeceras de seguridad duplicadas entre backend y proxy. | `backend/app/main.py`, `scripts/portal_proxy.py` | Políticas contradictorias (CSP, frame options). | Definir una única fuente de cabeceras antes de exponer la intranet (fuera de Fase A). |
| DU-09 | `Item.is_tool`, `is_returnable`, `is_consumable` vs futura entidad herramienta. | `master_data/models.py:57-59` | Riesgo de convertir una bandera en catálogo paralelo de herramientas. | Decidir D-09; si se crea `mnt.tool`, las banderas quedan como clasificación de catálogo, no como entidad. |
| DU-10 | `work_order_no` en req. requisición y en snapshot previsto de movimientos WMS. | `requisitions/models.py:55`, diseño B §8 | valor libre sin validación; se escribe en dos documentos. | Un único `work_order_no` inmutable por documento de origen; decidir D-10. |
| DU-11 | Recepción de compras (`pur.goods_receipt_line`) vs futura entrada WMS. | `purchasing/models.py:77+`, B.3 | Doble registro del mismo hecho físico → doble `CostLayer`. | B.3 debe extender, no duplicar: una recepción = un movimiento `RECEIPT` + una capa de costo. |
| DU-12 | `audit_log` (auditoría de acceso/acción) vs `document_event` vs bitácora de frontend. | `audit/models.py:13`, `documentation/models.py:97`, `features/history` | Tres versiones de “qué pasó” con actores distintos. | Definir canales: auditoría de seguridad, evento de documento, proyección de lectura. Contrato en Fase G. |

---

## 5. Funciones incompletas, stubs y ausencias críticas

| Elemento | Situación real | Consecuencia |
|---|---|---|
| `WMS_LOTE_B_ENABLED` | `False`; ningún router lo consume. | No hay movimientos WMS activos; B.0 es solo contrato. |
| `b7c8d9e0f1a2_lote_b_movimientos_wms.py` | No existe en `backend/migrations/versions/`. | No hay `inv.stock_balance_detail`, triggers, vistas ni backfill. |
| `inv.stock_movement` | Append-only solo por convención en servicios; sin trigger de base. | Un acceso directo a BD podría editar el hecho contable. |
| Reversos | `reversal_of_id` sin restricción de unicidad ni trigger. | Posible reverso duplicado o encadenado. |
| `audit.view_all` | Permiso fantasma (DU-06). | No asignable desde catálogo. |
| Entidad OT | Inexistente; solo texto `work_order_no`. | No se puede calcular costo por OT ni cerrar refacciones. |
| Entidad herramienta | Inexistente; solo banderas en ítem. | No hay responsable, préstamo ni calibración. |
| Factura de compra / triple match | Inexistentes. | Compras no declarables para producción. |
| CFDI/XML | Sin staging ni adaptador. | Integración CONTPAQi permanece aislada y sin activar. |
| IA | Sin código. | Fase H no iniciada; sin volumen autorizado. |
| Endpoints de dashboard | Inexistentes; KPIs en frontend. | Faltan fórmula, fuente, período y filtros verificables. |
| Generación/lectura QR | Solo `qr_token` texto. | No hay escaneo operativo. |
| Documentos desactualizados | `ARQUITECTURA.md` §14, `README.md`, `PRUEBAS_PORTAL.md` y `WMS_LOTE_B_PLAN.md` línea 5 ( línea base `bcf27bd`). | Riesgo de ejecutar un lote sobre supuestos equivocados. Usar siempre el HEAD verificado. |

---

## 6. Contradicciones documentales detectadas

| ID | Contradicción | Referencias | Criterio adoptado en Fase A |
|---|---|---|---|
| CO-01 | `bcf27bd` se presenta como línea base en `WMS_LOTE_B_PLAN.md`, pero HEAD real es `4a493b8`. | `WMS_LOTE_B_PLAN.md:5` vs `git log` | Prevalece Git: `4a493b8`. |
| CO-02 | El prompt B.1 del plan WMS crea tablas `wms.movement_order*`; el diseño y la puerta D-06 condicionan el esquema físico `wms`. | `WMS_LOTE_B_PLAN.md:371` vs `WMS_LOTE_B_DISENO.md:431-454` | No crear esquema `wms` sin aprobación; limitar B.1 a objetos `inv` si D-06 no está aprobada. |
| CO-03 | `WMS_LOTE_B_PLAN.md` B.10 cita 68 pruebas base; la línea base verificada es 77. | `WMS_LOTE_B_PLAN.md:287` | Usar 77 como regresión mínima. |
| CO-04 | `WMS_LOTE_B_PLAN.md` B.10 prevé `WMS_LOTE_B_RESULTADOS.md`; hoy existe `WMS_LOTE_B0_RESULTADOS.md`. | `WMS_LOTE_B_PLAN.md:292` | Crear el documento de resultados por lote sin sobrescribir B.0. |
| CO-05 | `ARQUITECTURA.md` §14 no refleja Lote A/B.0 ni el estado real de permisos. | `docs/ARQUITECTURA.md` | Actualizar en el lote que cambie contratos; no en Fase A. |

---

## 7. Decisiones pendientes que afectan la cobertura

Copia textual de `WMS_LOTE_B_DISENO.md` §12 (no se inventa aprobación):

1. Confirmar si las devoluciones deben descontar `line_delivered_qty` (en el diseño no: solo los reversos lo hacen).
2. Definir autorizador formal para liberación de cuarentena.
3. Definir si `expiry_date` vencida bloquea o solo advierte.
4. Decidir cuándo ejecutar `inv.backfill_lote_b_detail()` en el piloto.
5. Confirmar política FEFO vs FIFO por familia de artículo.

Decisiones adicionales derivadas de esta matriz: esquema físico `wms` (D-06), valuación y aprobadores (D-07), jerarquía de ubicación (D-08), modelo de herramientas (D-09), modelo OT (D-10), tolerancias de triple match (D-11) y canal CFDI (D-12). Detalle en `ERP_MRO_WMS_DEPENDENCIAS.md`.

---

## 8. Uso de esta matriz

- Todo prompt de lote debe citar el estado aquí registrado y no declarar terminada una capacidad marcada como PARCIAL, DISEÑO o AUSENTE.
- Las duplicidades DU-01…DU-12 se resuelven con migraciones aditivas y contratos, nunca borrando columnas ni datos.
- Los KPIs sin fuente verificable deben mostrarse como **SIN DATOS**; esta matriz no autoriza estimaciones.
- Para el orden de implementación y las puertas de aprobación, consultar `ERP_MRO_WMS_DEPENDENCIAS.md`.
