# WMS avanzado — Análisis comparativo y diagnóstico

**Fecha:** 2026-11-18

**Ruta:** `E:\ERP_MINERO`

**Estado:** DISEÑO. No se modificó código operativo.
**Referencias:** SAP EWM, IBM Maximo Manage, Dynamics 365 SCM, Oracle WMS, Manhattan Active WMS, Infor WMS y Blue Yonder WMS. Se toman **patrones funcionales públicamente conocidos**; no se copian interfaces, código ni componentes protegidos.

---

## 1. Propósito

Comparar las capacidades esperadas de un WMS/EAM de nivel empresarial con el estado real del ERP actual, para priorizar el diseño de un Almacén Minero Avanzado propio, integrable y progresivo.

**Regla de negocio vigente:** CONTPAQi Comercial Premium 11.5.1 continúa como sistema oficial de Almacén y Compras. El ERP mantiene un **espejo operativo**, no un segundo inventario oficial.

---

## 2. Estado real del ERP antes del diseño

| Aspecto | Evidencia |
|---|---|
| Commit actual | `c414ee9` (local, sin push) |
| Esquema | head Alembic `f4a7c1e2b3d6` |
| Tablas de negocio | **41** en 12 esquemas de dominio |
| Tabla técnica | `public.alembic_version` → 42 `BASE TABLE` en `information_schema` |
| Origen del “39 tablas” | Corresponde a Fase 3 (`f3a9c1d7b2e4`); Fase 4 añadió 2 tablas |
| Backend | FastAPI modular, 63 pruebas, ruff/mypy limpios |
| Frontend | React + TS, 9 pruebas, build correcto |
| Portal local | `http://127.0.0.1:8080`, 18/18 verificaciones |
| Piloto LAN | No creado / no activo; sin base `erp_minero_pilot` |

### 2.1 Esquemas y tablas existentes

| Esquema | Tablas | Dominio |
|---|---:|---|
| `seg` | 8 | usuarios, roles, permisos, sesiones, department scope |
| `org` | 5 | compañía, unidad minera, departamento, almacén, empleado |
| `mdm` | 3 | UOM, artículo, proveedor |
| `doc` | 5 | tipos, numeración, registro, eventos, idempotencia |
| `req` | 3 | requisición, línea, adjunto |
| `wfl` | 3 | solicitud, paso y decisión de aprobación |
| `inv` | 3 | saldo, movimiento, reserva |
| `pur` | 4 | OC, línea OC, recepción, línea recepción |
| `mnt` | 1 | equipo |
| `cost` | 2 | centro de costo, capa de costo |
| `intg` | 3 | sistema externo, outbox, inbox |
| `aud` | 1 | bitácora inmutable |

---

## 3. Matriz comparativa funcional

La escala de madurez del ERP es: **0** ausente, **1** embrionario, **2** parcial, **3** funcional básico, **4** avanzado.

| Capacidad WMS | Patrón en suites de referencia | Madurez actual | Brecha principal |
|---|---|---:|---|
| Catálogo maestro único | Artículo con atributos, UOM, equivalencias, proveedores y ciclo de vida | 2 | `mdm.item` sólo tiene código, tipo, UOM, flags de lote/serie y costo |
| Familias y equivalencias autorizadas | Clasificación jerárquica y sustituciones controladas | 0 | No hay familia ni tabla de equivalencias |
| UOM y conversiones | UOM base, compra, consumo y factores por artículo | 1 | Existen `uom` y `purchase_uom_id`, pero sin tabla de conversiones |
| Lotes, series y caducidades | FEFO, numeración de serie y trazabilidad por lote | 1 | Sólo flags booleanos y UUID centinela `NULL_UUID` |
| Ubicaciones jerárquicas | Almacén → zona → pasillo → anaquel → posición | 0 | `location_id` no tiene FK ni tabla maestra |
| Capacidad y restricciones | Reglas por zona, peso, temperatura y tipo de material | 0 | No modeladas |
| QR / código de barras | Identificación física y captura móvil | 0 | No hay tokens ni escaneo |
| Órdenes y tareas de movimiento | Oleadas, picking, putaway, tareas por operario | 0 | Los movimientos nacen directamente de documentos |
| Entradas por OC | Recepción contra OC, parciales e inspección | 3 | Existe recepción parcial con movimiento y capa de costo |
| Recepción por devolución/traspaso | Motivos documentados y destino controlado | 1 | Tipos de movimiento insuficientes |
| Salidas por requisición/OT | Consumo autorizado y descarga de costos | 3 | Requisición → reserva → entrega funciona |
| Salida por equipo/centro de costo | Imputación directa a objeto de costo | 2 | Requisición tiene equipo y centro, pero no asiento de costo |
| Quién entrega y recibe | Firma digital/responsable de custodia | 1 | Hay `created_by`, pero no par entrega/recepción |
| Traspasos y tránsito | Solicitud, preparación, despacho, tránsito, recepción parcial | 0 | Sin `transfer_id`, sin tipos `TRANSFER_IN/OUT`, sin saldo en tránsito |
| Inventarios físicos | Conteo general/cíclico/ABC/ciego, reconteo y aprobación | 0 | No hay plan, sesión ni líneas de conteo |
| Ajustes y conciliación | Diferencias con motivo y autorización | 1 | Existen tipos `ADJUSTMENT_*`, pero sin documento ni servicio |
| Herramientas retornables | Préstamos, resguardos, calibración y responsables | 1 | Sólo `mnt.equipment` como entidad simple |
| Costos valorizados | Costo promedio/FIFO, kardex valorizado, asientos | 2 | Hay `cost_layer`, sin `cost_posting` ni kardex valorizado |
| Reabastecimiento | Min/máx, punto de reorden, stock de seguridad | 0 | No hay reglas ni consumo histórico estructurado |
| Captura móvil | Escaneo, evidencia, validación de permisos | 0 | Fuera del alcance actual |
| Analítica operativa | Exactitud, rotación, cobertura, fill rate | 0 | Sin vistas ni agregados |
| IA y recomendaciones | Búsqueda semántica, duplicados, pronósticos, explicaciones | 0 | Sin datos ni pipelines |

---

## 4. Diagnóstico funcional

### 4.1 Fortalezas reutilizables

1. **Trazabilidad documental madura.** `doc.document_numbering`, `document_registry` y `document_event` con folio `TIPO-SERIE-AÑO-NNNNNN` y bloqueo `FOR UPDATE` (`shared/numbering.py:26-88`).
2. **Idempotencia atómica.** `shared/idempotency.py:24-75` usa `INSERT … ON CONFLICT DO NOTHING RETURNING`, no `SELECT` previo.
3. **Ledger de inventario.** `inv.stock_movement` registra dirección, tipo, cantidad, saldo posterior, documento origen, idempotencia y reversión.
4. **Reservas con vencimiento.** `inv.stock_reservation` con `consumed_qty`, estados y expiración.
5. **Integridad en base.** CHECK de no negatividad, `on_hand >= reserved`, unicidad por almacén/artículo/lote/ubicación y FK `RESTRICT`.
6. **Auditoría inmutable real.** Trigger `trg_audit_log_immutable` en Fase 3.
7. **RBAC con alcance.** Permisos granulares y departmentscope desde Fase 3.
8. **Outbox/inbox.** Eventos transaccionales ya modelados.
9. **Flujo de requisiciones probado.** Autorización por partida, anti-sobrereserva, entrega FIFO y cierre automático.
10. **Compras parciales.** OC, recepción parcial y capas de costo en la misma transacción.

### 4.2 Debilidades críticas

| ID | Debilidad | Impacto WMS |
|---|---|---|
| D-01 | Lote/serie/ubicación son UUID centinela sin FK | No hay FEFO, bin locator ni trazabilidad física real |
| D-02 | Sin órdenes/tareas de movimiento | No se puede preparar, asignar ni confirmar trabajo de almacén |
| D-03 | Traspasos no modelados | Imposible material en tránsito ni recepción parcial entre almacenes |
| D-04 | Sin conteos ni ajustes documentados | No hay exactitud de inventario ni conciliación controlada |
| D-05 | Sin asientos de costo por movimiento | Kardex valorizado y costos por OT/equipo incompletos |
| D-06 | Alcance RBAC no enforceado en inventario/compras | Riesgo de ver o mover stock de otra unidad minera |
| D-07 | Reversiones sólo metadato | No hay procedimiento controlado de contrapartidas |
| D-08 | Sin vistas de cantidades derivadas | `MODELO_DATOS.md:334-374` las describe, pero no existen en BD |
| D-09 | Listados sin paginación | No escala a catálogos y movimientos de WMS |
| D-10 | Nombres de CHECK con doble prefijo | Riesgo de desvío en futuros `autogenerate` de Alembic |
| D-11 | Outbox sin despachante | Los eventos se escriben, pero no se publican |
| D-12 | Sin triple match OC–recepción–factura | Bloqueo funcional heredado de Fase 4 |

---

## 5. Diagnóstico técnico

### 5.1 Arquitectura actual compatible con WMS

- Monolito modular FastAPI con esquemas PostgreSQL por dominio.
- Servicios transaccionales con `Session` y `SELECT … FOR UPDATE`.
- Reglas de cantidad en `NUMERIC(18,6)`/`NUMERIC(18,4)`; sin `float`.
- Misma transacción para negocio + auditoría + outbox.
- UI por features con cliente API tipado y CSRF.

### 5.2 Deuda técnica a corregir antes/durante el Lote A

1. Normalizar los nombres de CHECK con doble prefijo (`ck_*_ck_*`) detectados en Fase 4.
2. Crear la vista `req.v_requisition_line_quantities` o reemplazarla por funciones de servicio con contrato equivalente.
3. Añadir paginación y filtros obligatorios a los listados.
4. Aplicar `assert_department_access`/alcance de unidad minera a inventario y compras.
5. Definir si `warehouse.allows_negative` se elimina o se alinea con los CHECK incondicionales de `stock_balance`.
6. Definir el mecanismo de reintento para deadlocks/serialización en flujos multiagregado.

### 5.3 Restricciones que no deben romperse

- Un solo ledger de inventario: `inv.stock_movement`.
- CONTPAQi sigue siendo oficial; no se crea otro stock autoritativo.
- Movimientos append-only; correcciones por contrapartida.
- Toda escritura sensible lleva idempotencia, auditoría y evento.
- Sin conexión directa a CONTPAQi/GMAO.
- Sin exposición de red; desarrollo en `127.0.0.1`.
- Migraciones aditivas, sin `DROP`/`TRUNCATE`/`DELETE` masivo.

---

## 6. Cobertura por módulo solicitado

| Módulo | Ya existe | Ampliar | Nuevo |
|---|---|---|---|
| A. Catálogo maestro | Artículo, UOM, proveedor | Artículo con atributos | Familias, conversiones, equivalencias, relaciones artículo-proveedor, lote, serie |
| B. Ubicaciones | Almacén con 5 tipos | `stock_balance.location_id` | Jerarquía, restricciones, QR, plano 2D, reglas de sugerencia |
| C. Entradas | Recepción de OC parcial | Motivos y evidencia | Órdenes de entrada, inspección, cuarentena, devolución/traspaso/extraordinaria |
| D. Salidas | Entrega por requisición | Par entrega/recepción y costo | Salida por OT/equipo, devoluciones y cancelaciones controladas |
| E. Traspasos | Nada | Tipos de movimiento | Solicitud, autorización, despacho, tránsito, recepción y diferencias |
| F. Inventarios físicos | Nada | Ajustes como movimientos | Planes, sesiones, conteo ciego, reconteo, bloqueo y aprobación |
| G. Herramientas | `mnt.equipment` | Extensión del equipo | Préstamos, resguardos, calibración y responsables |
| H. Costos | Centro y capas | Movimiento con costo | Asientos, asignaciones, objetos de costo y aging |
| I. Reabastecimiento | Nada | Consumo de movimientos | Reglas, sugerencias y alertas |
| J. Captura móvil | Cliente API tipado | Permisos y esquemas | Escaneo, QR, evidencia y sesión móvil |
| K. Analítica | Bitácora y kardex básico | Índices y vistas | KPIs, exportación y dashboards |
| L. Inteligencia artificial | Nada | Datos sintéticos | Búsqueda, duplicados, pronósticos, anomalías y explicaciones |

---

## 7. Riesgos y dependencias

| Riesgo | Severidad | Dependencia |
|---|---|---|
| No creación de `erp_minero_pilot` | Alta | DBA autorizado |
| Ausencia de SDK/API oficial de CONTPAQi 11.5.1 | Alta | Proveedor/SOI |
| Datos reales no autorizados | Alta | Autorización por escrito |
| Concurrencia en saldos por ubicación/lote | Alta | Diseño de bloqueos del Lote B |
| Falta de definición de política de valuación | Alta | Contabilidad/Finanzas |
| Escala de catálogos y fotos | Media | Almacenamiento controlado |
| Datos insuficientes para IA | Media | Lote H y volumen histórico sintético |
| Alcance RBAC incompleto en inventario | Alta | Lote A/B |
| Deuda de nombres CHECK y vistas | Media | Pre-Lote A |

---

## 8. Decisiones pendientes

1. Confirmar el nuevo recuento: 41 tablas de dominio + `alembic_version`, no 39.
2. Aprobar el esquema de nombres para nuevas tablas WMS (reutilizar `mdm`/`inv`/`cost`/`intg` y un `wms` delgado para orquestación).
3. Definir si lotes/series son obligatorios por artículo desde el Lote A o se habilitan por configuración.
4. Definir jerarquía mínima de ubicación: zona → pasillo → anaquel → posición.
5. Definir política de valuación autorizada: promedio ponderado, FIFO u otra; **no inventar métodos**.
6. Definir quién aprueba diferencias de conteo y reversiones.
7. Definir si herramientas se modelan en `mnt` o en un subdominio WMS.
8. Confirmar que la IA sólo emitirá recomendaciones con aprobación humana.
9. Confirmar formato y canal autorizado para intercambio con CONTPAQi.
10. Confirmar si la prueba LAN se autoriza antes o después del Lote A.

---

## 9. Conclusión

El ERP tiene una base transaccional sólida para construir el WMS, pero carece de la capa física y documental que distingue a un almacén avanzado: ubicaciones, lotes/series reales, tareas, traspasos, conteos, herramientas, costos valorizados, reabastecimiento, captura móvil, analítica e IA. El Lote A debe atacar catálogos y ubicaciones sin tocar el ledger de stock, y debe corregir la deuda técnica que impediría migraciones limpias posteriores.
