# ERP MINERO INTEGRAL — Plan maestro MRO + WMS + Compras + IA

> Fase A ejecutada: auditoría de cobertura funcional y modelo de datos.
>
> Fecha: 2026-11-19
>
> Alcance de esta entrega: **solo documentación**. No se modificó código, no se aplicaron migraciones, no se hizo push ni despliegue.
>
> Estado: plan propuesto para aprobación por lote. **No declarar fases B–H como iniciadas.**

---

## 0. Verificación de la revisión real

No se asumió `bcf27bd` como HEAD. Estado comprobado con Git:

| Concepto | Valor observado |
|---|---|
| Rama | `main` |
| HEAD | `4a493b8` — `Agrega contratos, permisos y bandera del Lote B WMS` |
| Commit anterior | `b100013` — `Documenta arquitectura transaccional del Lote B WMS` |
| `bcf27bd` | `Moderniza requisiciones, autorizaciones y dashboard del portal local` (tercer commit hacia atrás; **no es HEAD**) |
| Árbol de trabajo | Limpio antes de iniciar Fase A |
| Push | Sin evidencia de rama remota ni push |
| Head de Alembic | `a1b2c3d4e5f6` (Lote A). La revisión B.1 `b7c8d9e0f1a2` **no existe** |

La línea base funcional real es, por tanto, `4a493b8`, no `bcf27bd`.

---

## 1. Principios rectores y restricciones

Fuente: `AGENTS.md`, `docs/ARQUITECTURA.md`, `docs/PERMISOS_RBAC.md`, documentos WMS.

1. Monolito modular FastAPI; routers bajo `/api/v1`; servicios → repositorios → SQLAlchemy.
2. CONTPAQi sigue siendo el inventario y la contabilidad oficiales. **Prohibida** conexión directa a su base.
3. Sierra Madre GMAO no se modifica ni se escriben sus tablas; solo referencias externas y eventos.
4. No crear un segundo inventario oficial: `inv.stock_movement` es el único hecho canónico; los saldos son proyecciones.
5. Migraciones aditivas. Prohibidos `DROP`, `TRUNCATE`, `DELETE` masivo y `alembic downgrade` sobre datos reales.
6. RBAC con alcance por compañía, unidad minera, departamento y almacén.
7. Auditoría, eventos (`outbox`) y numeración en la misma transacción que el cambio de negocio.
8. Idempotencia atómica con `INSERT ... ON CONFLICT DO NOTHING RETURNING`; nunca `SELECT` previo para decidir inserción.
9. `NUMERIC` para cantidades e importes; **sin `float`**. Cantidades `NUMERIC(18,6)`, importes `NUMERIC(18,2|4)`.
10. Solo datos sintéticos. Sin secretos en Git. Servidor local únicamente en `127.0.0.1`.
11. Sin sustituciones automáticas de artículos, sin compras autorizadas por IA y sin movimientos autónomos de IA.
12. Si faltan datos para un KPI: mostrar **SIN DATOS**, nunca estimar ni inventar.
13. Cada fase termina con pruebas ejecutadas localmente, documentación actualizada y commit local verificado. Sin push.
14. Si una regla de negocio no está aprobada, queda pendiente y la operación dependiente no se implementa.

---

## 2. Línea base verificada

### 2.1 Backend

- 12 módulos con modelos, 49 tablas en los esquemas `seg, org, mdm, doc, req, wfl, inv, pur, mnt, cost, intg, aud`.
- 55 operaciones HTTP: `health` (3, sin prefijo), `auth` (6), `admin` (13), `catalogs` (1), `requisitions` (11), `inventory` (6), `purchases` (6), `wms` (9), `audit` (1).
- Servicios implementados: identidad/RBAC, requisiciones, inventario heredado, compras base, catálogo WMS Lote A, auditoría, numeración, idempotencia y eventos.
- Sin implementar: movimientos WMS operativos, facturación/CFDI, triple match, entidad OT, entidad herramienta, motores de IA, endpoints de dashboard.
- `WMS_LOTE_B_ENABLED=False`; permisos y contratos B.0 registrados, sin router que los consuma.
- Cadena Alembic: `0001_initial_schema` → `d147e7ec92fb` → `f3a9c1d7b2e4` → `f4a7c1e2b3d6` → `a1b2c3d4e5f6`.

### 2.2 Frontend y portal

- React + TypeScript + Vite; 13 pantallas en 11 features; cliente API manual `api.*` (no generado desde OpenAPI), sin `fetch` directo en componentes.
- Dashboard con KPIs reales calculados desde la API; panel explícito de “Indicadores no disponibles con la API actual”. No hay números inventados.
- QR del Lote A: solo `qr_token` como texto; sin generación gráfica ni lectura.
- Portal local: backend `127.0.0.1:8000`, proxy `127.0.0.1:8080`, Vite desarrollo `127.0.0.1:5173`. `PORTAL_ALLOW_LAN=false`.
- Pruebas: 77 backend, 25 frontend; verificación smoke de portal con datos sintéticos.

### 2.3 Documents rectores

`AGENTS.md`, `ARQUITECTURA.md`, `MODELO_DATOS.md`, `PLAN_IMPLEMENTACION.md`, `PLAN_SIGUIENTE_DESARROLLO.md`, `PERMISOS_RBAC.md`, `FLUJO_REQUISICIONES.md`, serie `WMS_*` y `WMS_LOTE_B0_RESULTADOS.md`. Detalle en `ERP_MRO_WMS_MATRIZ_FUNCIONAL.md` y `ERP_MRO_WMS_DEPENDENCIAS.md`.

---

## 3. Mapa de fases

| Fase | Nombre | Objetivo principal | Depende de | Estado |
|---|---|---|---|---|
| A | Auditoría y modelo de datos | Cobertura real, duplicidades, dependencias y criterios | — | **Ejecutada en esta entrega** |
| B | Cierre del WMS transaccional | Completar Lote B (B.1–B.10) y cimentar C | A + decisiones D-01…D-05 | B.0 completo; B.1–B.10 pendientes |
| C | MRO avanzado y compatibilidad por equipo | Maestro MRO enriquecido, equivalencias, sustitutos y compatibilidad | B.2/B.4 + decisión de jerarquía MRO | Solo diseño parcial |
| D | Inventario inteligente | Indicadores calculados, alertas, ABC/XYZ, cobertura y stock de seguridad | B completo + consumos históricos | Solo diseño |
| E | Compras completas y triple match | RFQ, comparativos, OC–recepción–factura, tolerancias y CFDI aislado | B.3 + decisión de tolerancias y aprobadores | OC/recepciones base existen; triple match ausente |
| F | Refacciones por OT y herramientas | Consumo por OT/equipo y control de herramientas retornables | B.4 + modelo OT + modelo herramienta | `work_order_no` text; `is_tool` sin entidad |
| G | Dashboard ejecutivo | Paneles por rol con fórmula, fuente, período y filtros | B, D, E, F | Dashboard operativo básico existe |
| H | IA predictiva | Reglas verificables y modelos con revisión humana | D + E + G + volumen de datos | Solo principios normativos |

---

## 4. Detalle por fase

### Fase A — Auditoría y modelo de datos **(ejecutada)**

| Apartado | Contenido |
|---|---|
| Alcance | Inspección del repositorio, módulos, endpoints, migraciones, frontend, pruebas y documentos WMS; matriz de los 9 módulos; duplicidades; dependencias; criterios de aceptación. |
| Dependencias | Ninguna. |
| Riesgos | Documentación desactualizada (`ARQUITECTURA.md` §14, `README.md`, `PRUEBAS_PORTAL.md`), contradicciones entre documentos WMS. |
| Migraciones | Ninguna. |
| API | Ninguna. |
| Interfaz React | Ninguna. |
| RBAC | Solo lectura del catálogo existente. |
| Pruebas | No se ejecutaron en esta fase: no hubo cambios de código. |
| Documentación | `ERP_MRO_WMS_PLAN_MAESTRO.md`, `ERP_MRO_WMS_MATRIZ_FUNCIONAL.md`, `ERP_MRO_WMS_DEPENDENCIAS.md`. |
| Commit | Commit local del documento, sin push. |
| Criterios de aceptación | Los tres documentos existen; HEAD real verificado; sin cambios de código; sin push. |

---

### Fase B — Cierre del WMS transaccional

| Apartado | Contenido |
|---|---|
| Alcance | Ejecutar B.1–B.10 del plan existente: migración aditiva, modelos/repositorio, entradas, salidas, devoluciones/cuarentena, reversos, kardex, auditoría/RBAC, frontend mínimo y verificación. Después, Lote C (traspasos, transferencias y material en tránsito). |
| Dependencias | Lote A; B.0 completado; decisiones D-01…D-05; definición del esquema físico `wms` (AD-01). |
| Riesgos | R01–R22 de `WMS_LOTE_B_RIESGOS.md`: doble salida, divergencia de proyecciones, deadlocks, reversos duplicados, sobre-recepción, devolución excesiva, cuarentena, RBAC de alcance. |
| Migraciones | `b7c8d9e0f1a2_lote_b_movimientos_wms.py`, `down_revision = a1b2c3d4e5f6`. Aditiva; `downgrade()` con `RuntimeError`; sin backfill automático. |
| API | `POST /api/v1/wms/movements/{receipts,issues,returns,quarantine,reversals}`; `GET /wms/movements/{kardex,balances,reconciliation}`. Registro condicional a `WMS_LOTE_B_ENABLED`. |
| Interfaz React | `frontend/src/features/wms/` y `inventory/`: saldos detallados, entradas, salidas, devoluciones, reversos y kardex con filtros. Cliente tipado. |
| RBAC | Permisos B.0 ya registrados; cablear `require_permission` y filtro por unidad/departamento/almacén en B.8. |
| Pruebas | Matriz C01–C20 con PostgreSQL real, datos sintéticos y concurrencia; `empty→head` en base sintética; regresión de las 77 pruebas. SQLite inválido. |
| Documentación | `WMS_LOTE_B_RESULTADOS.md` (nombre previsto en el plan B.10; hoy existe `WMS_LOTE_B0_RESULTADOS.md`) y evidencia por lote. |
| Commit | Un commit local por lote B.1…B.10, mensaje en español e imperativo. Sin push. |
| Criterios de aceptación | Agregado y detalle reconcilian a cero; un solo movimiento por intención física; todo movimiento con documento, idempotencia, auditoría y evento; reversos/ devoluciones referencian origen; kardex filtrable; trigger de inmutabilidad verificado en base; 20 escenarios C01–C20 en verde; bandera apagada hasta autorización. |

---

### Fase C — MRO avanzado y compatibilidad por equipo

| Apartado | Contenido |
|---|---|
| Alcance | Enriquecer `mdm.item`: código interno único, OEM/fabricante, marca, familia/subfamilia, descripción normalizada, UOM, equivalencias autorizadas/no autorizadas, compatibilidad por modelo y equipo, fotos/fichas/manuales, proveedores, historial de cambios, duplicados sugeridos, obsoletos y sustitutos aprobados. Sin sustitución automática. |
| Dependencias | B.2 (repositorio), B.4 (salidas con snapshot), decisión de jerarquía mínima y obligatoriedad de lote/serie por familia. |
| Riesgos | Duplicidad de catálogos, sustituciones no autorizadas, deriva de descripciones, centroid de datos de GMAO. |
| Migraciones | Aditivas: columnas y tablas de equivalencias, compatibilidad, historial y sustitutos en `mdm`. Sin borrar `mdm.item`. |
| API | `GET/POST /api/v1/mro/items`, `/equivalences`, `/compatibility`, `/changes`, `/duplicates`, `/supersession`; búsqueda MRO para `ItemPicker`. |
| Interfaz React | `features/mro/`: ficha técnica extendida, comparador de equivalencias, alerta de duplicados, gestor de sustitutos con aprobación. |
| RBAC | Permisos `mro.*` con alcance por unidad/almacén; solo aprobador puede activar equivalencias/sustitutos. |
| Pruebas | Unicidad de código interno, precisión de equivalencias, rechazo de sustitución sin permiso, historial append-only, regresión WMS Lote A. |
| Documentación | `MRO_MODELO_DATOS.md`, `MRO_REGLAS_NEGOCIO.md`, resultados de fase. |
| Commit | Local, por lote MRO. Sin push. |
| Criterios de aceptación | Un código interno por artículo; equivalencias y sustitutos requieren aprobación explícita; historial inmutable; ninguna sustitución automática en movimientos; búsqueda MRO con filtros por equipo/modelo. |

---

### Fase D — Inventario inteligente

| Apartado | Contenido |
|---|---|
| Alcance | Separar **indicadores calculados** de **predicciones**: físico/disponible/reservado, por almacén y ubicación, máximos/mínimos, stock de seguridad, punto de reorden, criticidad por equipo, ABC/XYZ, cobertura, consumo histórico, tiempos de reposición, recomendaciones y alertas; control de inmovilizados. |
| Dependencias | Fase B completa; consumos históricos reales o sintéticos autorizados; parámetros aprobados de criticidad y reposición. |
| Riesgos | Mezclar hechos con estimaciones; KPIs con datos insuficientes; umbrales no aprobados; doble inventario. |
| Migraciones | Aditivas: parámetros de reposición, clasificación y snapshots de consumo. Solo lectura sobre `inv.stock_movement`. |
| API | `GET /api/v1/inventory-intelligence/{balances,coverage,abc-xyz,alerts,slow-moving,replenishment}`; respuesta con `computed_at`, `source`, `period`, `filters` y `data_status=SIN DATOS` cuando corresponda. |
| Interfaz React | `features/inventory-intelligence/`: tablas de cobertura, alertas, clasificación y recomendaciones; etiqueta visible “calculado” vs “predicción”. |
| RBAC | Consulta por almacén/unidad; escritura de umbrales solo con permiso de administración de inventario y auditoría. |
| Pruebas | Cálculo determinista de disponible/cobertura/rotación; cero escritura en saldos; `SIN DATOS` sin histórico; regresión concurrente de B. |
| Documentación | `INVENTARIO_INTELIGENTE_KPIS.md` con fórmula, fuente, período y filtros por indicador. |
| Commit | Local, por lote. Sin push. |
| Criterios de aceptación | Indicadores calculados reproducibles desde movimientos; predicciones claramente separadas y explicadas; sin umbrales inventados; alertas trazables; ningún indicador modifica stock. |

---

### Fase E — Compras completas y triple match

| Apartado | Contenido |
|---|---|
| Alcance | RFQ, comparativos, precios/plazos, selección justificada, OC, aprobaciones por importe, entregas parciales, devoluciones a proveedor, evaluación, triple match OC–recepción–factura, documentación CFDI/XML por integración autorizada y compromisos de gasto. |
| Dependencias | B.3 (recepciones enriquecidas); decisión de tolerancias, aprobador de diferencias y política de importes; integración CONTPAQi aislada y autorizada. |
| Riesgos | Pagar sin recepción; doble `CostLayer`; factura huérfana; exposición de CFDI real; tolerancias inventadas. |
| Migraciones | Aditivas: `pur.rfq`, `pur.quote`, `pur.invoice`, `pur.match_result`, `pur.supplier_score`, `intg` staging de documentos. Sin tablas de CONTPAQi. |
| API | `POST/GET /api/v1/purchases/rfq`, `/quotes`, `/award`, `/invoices`, `/match`, `/supplier-evaluation`, `/commitments`. Mantener todos los endpoints actuales. |
| Interfaz React | `features/purchases/`: comparativo, aprobación por importe, panel de triple match con diferencias y motivo, devoluciones a proveedor, seguimiento de compromisos. |
| RBAC | `purchase.*` existente más nuevos; segregación entre aprobar OC, recibir y aprobar diferencias. Alcance por unidad/departamento. |
| Pruebas | PostgreSQL real: triple match conforme, tolerancia aprobada, discrepancia rechazada, recepción parcial, devolución, idempotencia de GRN, `CostLayer` único por línea, concurrencia de recepciones. |
| Documentación | `COMPRAS_TRIPLE_MATCH.md`: reglas, tolerancias autorizadas, evidencia y estados. |
| Commit | Local, por lote. Sin push. |
| Criterios de aceptación | Ninguna factura se liquida sin OC + recepción + match en verde; diferencias requieren aprobador formal; CFDI solo vía staging autorizado; **no se declara compras lista para producción** sin triple match y conciliación. |

---

### Fase F — Refacciones por OT y herramientas

| Apartado | Contenido |
|---|---|
| Alcance | Asociación OT–requisición, planeado/reservado/entregado/devuelto/consumido, costo por OT y equipo, historial de materiales, compatibilidad con el equipo, comparación planeado vs real. Herramientas: catálogoindividual, serie, QR, responsable, préstamo, resguardo, devolución, condición, extravío, daño, calibración y vencimientos. Separar retornables de consumibles. |
| Dependencias | B.4 (salidas con `work_order_no`, equipo y centro de costo); decisión formal de modelo OT y de modelo herramienta (activo vs consumible, `mnt` vs WMS); B.0/E para préstamos con responsable. |
| Riesgos | Inventar OT local sin aprobación; escribir en GMAO; mezclar herramienta con repuesto consumible; préstamo sin responsable; mezclar consumo planeado y real. |
| Migraciones | Aditivas: referencia OT (texto validado o entidad autorizada), líneas de refacción por OT, `mnt.tool`, `mnt.tool_loan`, `mnt.tool_calibration`. Sin tablas GMAO. |
| API | `GET/POST /api/v1/maintenance/ot-refs`, `/planned-parts`, `/issues`, `/returns`, `/costs`, `/tools`, `/loans`, `/calibrations`. Integración futura solo con `external_gmao_id` y eventos. |
| Interfaz React | `features/maintenance/`: ficha OT (planeado vs real), consumo por equipo, módulo de herramientas con QR y responsable. |
| RBAC | `maintenance.*` y `tools.*`; responsable y cuadrilla con alcance; solo aprobador cierra préstamos/calibraciones. |
| Pruebas | Consumo real = entregas − devoluciones; costo por OT/equipo; compatibilidad rechazada; préstamo con responsable activo; alerta de calibración vencida; ninguna escritura GMAO. |
| Documentación | `REFACCIONES_OT.md`, `HERRAMIENTAS_MODELO.md`. |
| Commit | Local, por sublote (OT y herramientas por separado). Sin push. |
| Criterios de aceptación | Sin entidad OT inventada sin aprobación; `work_order_no` inmutable en movimientos; retornables y consumibles separados; historial append-only; cero conexión a GMAO. |

---

### Fase G — Dashboard ejecutivo

| Apartado | Contenido |
|---|---|
| Alcance | Paneles de Gerencia, Almacén, Compras, Mantenimiento y Administración con: inventario valorizado, rotación, exactitud, sin movimiento, faltantes, nivel de servicio, compras pendientes, entregas parciales, consumo por equipo, costo por OT, presupuesto vs gasto, riesgo de desabasto y productividad de almacén. |
| Dependencias | B, D, E, F; contratos de KPI con fuente y período; datos autorizados. |
| Riesgos | KPIs inventados, fórmulas divergentes entre frontend y backend, consumo de datos de producción, mezcla de predicciones con hechos. |
| Migraciones | Preferentemente vistas/SQL de solo lectura; si se materializan snapshots, migraciones aditivas con `computed_at`. |
| API | `GET /api/v1/dashboard/{executive,warehouse,purchases,maintenance,admin}`; cada respuesta incluye `formula`, `source`, `period`, `filters`, `value|null`, `status`. |
| Interfaz React | Unificar los tres renderizados de bitácora y los cuatro de historial en componentes compartidos; panel por rol; estado `SIN DATOS` explícito. |
| RBAC | Cada panel exige permiso y alcance; el backend filtra, la UI solo oculta. |
| Pruebas | Contrato KPI ↔ respuesta real; fórmulas con datos sintéticos; `SIN DATOS`; regresión de dashboard actual y portal smoke. |
| Documentación | `DASHBOARD_KPIS.md`: tabla por indicador con fórmula, fuente, período, filtros y rol. |
| Commit | Local. Sin push. |
| Criterios de aceptación | Todo KPI tiene fórmula, fuente, período y filtros documentados; sin dato suficiente muestra `SIN DATOS`; ningún KPI calculado en componentes criticos sin contrato backend; portal smoke en verde. |

---

### Fase H — IA predictiva

| Apartado | Contenido |
|---|---|
| Alcance | Pronóstico de consumo, riesgo de desabasto, consumo anormal, sugerencias de máximos/mínimos, detección de duplicados MRO, reabastecimiento, comportamiento por equipo y explicaciones. Primero reglas deterministas y verificables; modelos solo con histórico suficiente. |
| Dependencias | D, E, G; volumen histórico autorizado; políticas aprobadas de reabastecimiento y aprobación humana. |
| Riesgos | Recomendación autónoma, explicaciones incompletas, sesgo con datos sintéticos, umbrales inventados, falsa precisión. |
| Migraciones | Aditivas: `intg.ai_recommendation` con `rule_version`, `input_snapshot`, `confidence`, `reason`, `human_decision`. Sin escritura en `inv` ni `pur`. |
| API | `GET /api/v1/ai/{forecast,stockout-risk,anomalies,replenishment,duplicates,explanations}`; `POST /api/v1/ai/recommendations/{id}/decision` solo para registro de decisión humana. |
| Interfaz React | `features/ai/`: recomendaciones con motivo, evidencia, confianza y versión; botón de disposición humana; sin botones que ejecuten movimientos. |
| RBAC | Solo lectura para la mayoría; registro de decisión con permiso de aprobador; auditoría obligatoria. |
| Pruebas | Reglas deterministas con datos sintéticos; abstención por volumen insuficiente; recomendación no modifica stock/OC; explicación presente; disposición humana auditada. |
| Documentación | `IA_REGLAS_Y_MODELOS.md`, `IA_EXPLICABILIDAD.md`. |
| Commit | Local, por lote. Sin push. |
| Criterios de aceptación | La IA no autoriza compras, no modifica inventario y no ejecuta movimientos; toda recomendación lleva explicación, versión y evidencia; sin volumen suficiente responde “datos insuficientes”; aprobación humana registrada. |

---

## 5. Puertas de decisión

Las operaciones dependientes de estas decisiones **no se implementan** hasta aprobación explícita. Detalle en `ERP_MRO_WMS_DEPENDENCIAS.md`.

| ID | Decisión | Fase bloqueada |
|---|---|---|
| D-01 | ¿Las devoluciones descuentan `line_delivered_qty`? | B.5 |
| D-02 | Autorizador formal de liberación de cuarentena | B.5/B.8 |
| D-03 | `expiry_date` vencida: ¿bloquea o advierte? | B.3/B.4 |
| D-04 | Momento de ejecutar `inv.backfill_lote_b_detail()` en piloto | B.1/B.10 |
| D-05 | FEFO vs FIFO por familia de artículo | B.4/D |
| D-06 | Esquema físico `wms` vs esquemas actuales | B.1 |
| D-07 | Política de valuación y aprobadores de diferencias/reversiones | B/F/E |
| D-08 | Modelo de jerarquía de ubicación y reglas de mezcla | B/C |
| D-09 | Modelo de herramientas (activo/consumible/retornable; `mnt` o WMS) | F |
| D-10 | Modelo OT local vs solo `work_order_no` externo | F |
| D-11 | Tolerancias y aprobador de triple match | E |
| D-12 | Formato/canal CFDI con CONTPAQi y momento de prueba LAN | E |

---

## 6. Reglas de ejecución por lote

1. Verificar `git status` y HEAD real antes de editar.
2. Leer `AGENTS.md`, este plan, la matriz funcional y el documento de dependencias.
3. Trabajar solo en el alcance del lote; un commit local por lote, mensaje en español, imperativo y específico.
4. No tocar CONTPAQi, GMAO, datos reales, migraciones aplicadas, firewall ni red.
5. Usar PostgreSQL real para transacciones y concurrencia; nunca SQLite para afirmar una prueba PostgreSQL.
6. Agregar pruebas junto al código; ejecutar `pytest`, `ruff`, `mypy`; frontend/build/portal solo si hay cambios frontend.
7. Revisar `git diff` antes del commit: sin secretos, sin datos reales, sin `0.0.0.0`, sin patrones destructivos.
8. Actualizar documentación y declarar explícitamente limitaciones y siguiente lote.
9. No declarar terminado un módulo si falta prueba, migración verificada o aprobación de decisión dependiente.

---

## 7. Definición de terminado

Todo lote debe cumplir:

- Código compila; lint y type-check limpios.
- Pruebas nuevas y existentes pasan localmente; PostgreSQL real cuando haya transacciones.
- Migración, si aplica, aditiva y probada de `empty` a `head` en base sintética.
- Sin secretos ni datos reales en el diff.
- Bitácora y eventos cubren las acciones sensibles nuevas.
- Documentación relevante actualizada.
- Limitaciones, decisiones pendientes y siguiente lote indicados.
- Commit local verificado, sin push.

---

## 8. Instrucción para el siguiente lote de OpenCode

**Lote siguiente recomendado: Fase B — Lote B.1 (migración aditiva), condicionado a la puerta D-06.**

```text
Trabaja en E:\ERP_MINERO. Lee AGENTS.md, docs/ERP_MRO_WMS_PLAN_MAESTRO.md,
docs/ERP_MRO_WMS_MATRIZ_FUNCIONAL.md, docs/ERP_MRO_WMS_DEPENDENCIAS.md y
docs/WMS_LOTE_B_PLAN.md antes de cambiar código.

Verificación inicial obligatoria:
1. Confirma con git log que HEAD es 4a493b8 o posterior y que git status está limpio.
2. Confirma que WMS_LOTE_B_ENABLED=False y que no existen rutas /api/v1/wms/movements.
3. Confirma que la decisión D-06 (esquema físico wms) está aprobada por escrito.
   Si NO está aprobada, NO crees tablas en el esquema wms: limita el lote a
   inv.stock_balance_detail, columnas de inv.stock_movement, índices parciales,
   triggers de inmutabilidad/reverso/reconciliación, vistas de kardex y de
   reconciliación, y función manual inv.backfill_lote_b_detail(). Reporta el bloqueo.

Implementa:
4. Crea backend/migrations/versions/b7c8d9e0f1a2_lote_b_movimientos_wms.py con
   down_revision = a1b2c3d4e5f6. Solo DDL aditivo; downgrade() lanza RuntimeError.
5. No ejecutes backfill automático, no modifiques datos y no toques CONTPAQi/GMAO.
6. Crea backend/tests/integration/test_migration_lote_b.py con:
   - verificación de objetos creados (columnas, índice, triggers, vistas),
   - intento de UPDATE/DELETE sobre inv.stock_movement que debe fallar,
   - reverso duplicado que debe fallar,
   - COMMIT con divergencia agregado/detalle que debe fallar.
7. Ejecuta la migración únicamente sobre la base sintética de pruebas y ejecuta
   pytest, ruff y mypy. No uses SQLite. No hagas push.
8. Crea docs/WMS_LOTE_B1_RESULTADOS.md con objetos creados, pruebas ejecutadas,
   Decisiones pendientes D-01…D-05 y siguiente lote B.2.
9. Haz un commit local en español, imperativo y específico. Sin push.

Detén solamente la operación que dependa de una decisión no aprobada y continúa
con las actividades independientes y seguras. No declares el Lote B completo.
```

---

## 9. Limitaciones conocidas

- `erp_minero_pilot` no existe; la verificación `empty→head` requiere autorización administrativa y rol con `CREATEDB`.
- No hay CI; las verificaciones son locales.
- El servicio PostgreSQL local tuvo una terminación anómala documentada durante B.0; verificar estabilidad antes de B.1.
- No hay volumen histórico autorizado para IA; Fase H debe comenzar con reglas deterministas y abstención.
- Ningún documento autoriza producción, LAN, TLS ni integraciones externas activas.
