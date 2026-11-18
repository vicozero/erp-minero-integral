# Plan de implementación — ERP MINERO INTEGRAL

**Versión:** 0.1  
**Fecha:** 2026-11-18  
**Principio:** Lotes pequeños, verificables y reversibles en documento. Ningún lote se declara terminado sin pruebas.

---

## 1. Reglas de planeación

1. Un lote no comienza hasta que el anterior cumple sus criterios de salida.
2. Cada tarea tiene un entregable observable: archivo, migración, endpoint o prueba.
3. Las migraciones son aditivas; no se eliminan columnas ni tablas.
4. Los datos de prueba son sintéticos.
5. El servidor solo escucha en `127.0.0.1`.
6. No se conecta a CONTPAQi ni a Sierra Madre GMAO.
7. No se publica contabilidad ni stock a sistemas externos.
8. La UI se construye después de que el contrato API esté probado.
9. Cada cambio sensible genera bitácora en la misma transacción.
10. Si una tarea crece más de lo previsto, se divide; no se “aprovecha” para refactorizar otros dominios.

> Nota: este documento usa terminología en español en todos sus conceptos.

---

## 2. Roadmap general

| Lote | Nombre | Entregable principal | Criterio de salida |
|---|---|---|---|
| 0 | Diseño y reglas | `AGENTS.md` y documentos técnicos | Documentos creados y revisados |
| 1 | Cimientos técnicos | Backend/frontend mínimos, Alembic, auth, auditoría, numeración | `pytest`, `npm run build`, `alembic upgrade head`, health check local |
| 2 | Organización y maestros | Catálogos sintéticos y CRUD | Pruebas de unicidad y RBAC por alcance |
| 3 | Requisiciones y aprobación | Ciclo DRAFT→APPROVED con decisiones por línea | Pruebas de límites de cantidad y workflow |
| 4 | Inventario operativo | Reservas, movimientos, ajustes, conciliación interna | Pruebas de concurrencia, idempotencia y rollback |
| 5 | Compras | OC, recepciones, facturas y triple match | Recepción genera stock+costo atómicamente |
| 6 | Equipos y mantenimiento | Equipos, medidores, OT y consumo | Consumo vinculado a movimiento real |
| 7 | Costos y valuación | Asientos, capas FIFO/promedio, asignaciones | Pruebas de reversión y conciliación de capas |
| 8 | Integración controlada | Staging, snapshots, outbox/inbox y reportes de conciliación | Sin conexión directa; hashes y bitácora verificados |
| 9 | Experiencia de usuario | Pantallas React por dominio | Playwright local cubre flujos críticos |
| 10 | Endurecimiento intranet | Solo tras autorización | No se ejecuta en este proyecto inicial |

---

## 3. Detalle de lotes

### Lote 0 — Diseño y reglas

**Estado:** completado en esta sesión.

| Tarea | Resultado |
|---|---|
| Inspeccionar ubicación | Sin archivos preexistentes; sin prototipo |
| Redactar reglas del proyecto | `AGENTS.md` |
| Documentar arquitectura | `docs/ARQUITECTURA.md` |
| Documentar modelo de datos | `docs/MODELO_DATOS.md` |
| Definir plan y riesgos | Este documento |
| Definir primer lote | `docs/PRIMER_LOTE_OPENCODE.md` |

**Criterio de salida:** documentos creados sin modificar sistemas externos ni infraestructura.

---

### Lote 1 — Cimientos técnicos

Ver `docs/PRIMER_LOTE_OPENCODE.md` para los prompts exactos.

| # | Tarea | Verificación |
|---|---|---|
| 1.1 | Inicializar estructura de repositorio, `.gitignore` y `.env.example` | Sin secretos en diff; `git status` limpio tras commit |
| 1.2 | Configuración central con Pydantic Settings | Prueba de variables requeridas y valores por defecto |
| 1.3 | Base declarativa SQLAlchemy 2 y naming convention | Prueba de nombres de constraints |
| 1.4 | Alembic inicial con 12 esquemas y tablas transversales | `alembic upgrade head` desde base vacía |
| 1.5 | Endpoint `/health` y `/api/v1/status` | Prueba HTTP 200 local |
| 1.6 | Usuario/rol/permiso mínimo y login local | Prueba login correcto/incorrecto; hash no expuesto |
| 1.7 | Middleware de `request_id` y bitácora | Prueba de que una acción sensible escribe `aud.audit_log` |
| 1.8 | Servicio de numeración documental | Prueba concurrente de números únicos |
| 1.9 | Esqueleto React con layout y página de estado | `npm run build` y prueba de render |
| 1.10 | Comandos de verificación local documentados | `README.md` con comandos sin red |

**Criterio de salida:** base técnica ejecutable localmente; aún sin flujos de negocio completos.

---

### Lote 2 — Organización y datos maestros

| # | Tarea | Verificación |
|---|---|---|
| 2.1 | Modelos y migración de `org.company`, `mining_unit`, `department`, `warehouse`, `employee` | FK y UNIQUE probados |
| 2.2 | Modelos y migración de `mdm.uom`, `item`, `supplier`, `lot`, `serial`, `mining_location` | CHECK de `item_type` y trazabilidad por lote/serie |
| 2.3 | Semilla sintética de catálogos | Ningún dato real; prueba de idempotencia de seed |
| 2.4 | CRUD con paginación y filtros | Contratos OpenAPI estables |
| 2.5 | RBAC con alcance por unidad/almacén | Usuario de almacén A no ve almacén B |
| 2.6 | Bitácora de altas/cambios de catálogos | `audit_log` contiene antes/después |

**Criterio de salida:** catálogos disponibles para requisiciones y compras.

---

### Lote 3 — Requisiciones y autorizaciones

| # | Tarea | Verificación |
|---|---|---|
| 3.1 | Migración de requisición, línea y asignación de costos | UNIQUE `(requisition_id, line_no)` |
| 3.2 | Servicio de creación con validación de líneas | Rechaza requisición vacía y cantidades ≤ 0 |
| 3.3 | Máquina de estados DRAFT/SUBMITTED/APPROVED/REJECTED/CANCELLED/CLOSED | Prueba de transiciones inválidas |
| 3.4 | Políticas y pasos de aprobación | Prueba de selección de política por monto/tipo |
| 3.5 | Decisiones por línea con `approved_qty` | Suma nunca excede solicitado-cancelado |
| 3.6 | Vista `req.v_requisition_line_quantities` | Prueba con datos sintéticos |
| 3.7 | Eventos documentales y notificación interna local | Sin envío externo; solo outbox local |

**Criterio de salida:** flujo de autorización auditado y probado; aún sin movimientos de stock.

---

### Lote 4 — Inventario operativo

| # | Tarea | Verificación |
|---|---|---|
| 4.1 | Migración de saldos, movimientos, reservas y ajustes | CHECK de cantidades no negativas |
| 4.2 | Servicio de reserva con `FOR UPDATE` | Dos reservas concurrentes no sobreasignan stock |
| 4.3 | Servicio de entrega consume reserva y crea movimiento | Rollback de costos revierte movimiento |
| 4.4 | Recepciones internas y devoluciones | Dirección IN/OUT coherente |
| 4.5 | Transferencias entre almacenes con dos movimientos | Mismo `transfer_id`, stock total conservado |
| 4.6 | Ajustes con motivo y aprobación | Ningún movimiento anterior se modifica |
| 4.7 | Idempotencia y reintentos | Misma clave no duplica movimientos |
| 4.8 | Snapshots y reconciliación interna | Diferencias registradas, no borradas |

**Criterio de salida:** inventario operativo confiable, explícitamente no oficial.

---

### Lote 5 — Compras

| # | Tarea | Verificación |
|---|---|---|
| 5.1 | Migración de OC, líneas, recepciones, facturas y tolerancias | FK a requisición línea |
| 5.2 | Generar OC desde líneas autorizadas | No excede `authorised_qty` |
| 5.3 | Aprobación de OC con workflow existente | OC no aprobada no se puede enviar |
| 5.4 | Registro de recepción que crea movimiento y capa de costo | Transacción única verificada |
| 5.5 | Factura y triple match | Diferencia fuera de tolerancia bloquea cierre |
| 5.6 | Reporte de OC por recibir | Consulta con índices y prueba de rendimiento básica |

**Criterio de salida:** ciclo compra→recepción→costo trazable.

---

### Lote 6 — Equipos y mantenimiento

| # | Tarea | Verificación |
|---|---|---|
| 6.1 | Migración de equipos, medidores y lecturas | `asset_tag` único |
| 6.2 | Migración de OT, tareas y consumo de materiales | FK a movimiento |
| 6.3 | Máquina de estados de OT | Transiciones inválidas rechazadas |
| 6.4 | Consumo desde requisición aprobada | Genera salida de stock y asiento |
| 6.5 | Referencias a GMAO sin conexión | `external_gmao_id` y eventos locales; prueba sin red |

**Criterio de salida:** mantenimiento consume inventario con trazabilidad y sin escribir en GMAO.

---

### Lote 7 — Costos y valuación

| # | Tarea | Verificación |
|---|---|---|
| 7.1 | Migración de centros/objetos de costo, asientos y capas | Suma de asignación = 100 |
| 7.2 | Valuación FIFO y promedio ponderado | Pruebas unitarias comparativas |
| 7.3 | Asiento automático por consumo y recepción | Un movimiento = un asiento equivalente |
| 7.4 | Reversión por contrapartida | Original intacto |
| 7.5 | Reporte por centro de costo/unidad minera | Datos sintéticos y totales cuadrados |

**Criterio de salida:** costos operativos consistentes; sin publicación fiscal.

---

### Lote 8 — Integración controlada

| # | Tarea | Verificación |
|---|---|---|
| 8.1 | Catálogo de sistemas externos y mapeos | CONTPAQi marcado como oficial, GMAO no |
| 8.2 | Carga de archivos a staging con SHA-256 | Hash y bitácora verificados |
| 8.3 | Validación fila por fila y reporte de errores | Archivo inválido no contamina tablas finales |
| 8.4 | Snapshots de conciliación | Diferencias por artículo/lote |
| 8.5 | Outbox/inbox con reintentos | Evento duplicado no produce doble efecto |
| 8.6 | Documento de operación de importación | Sin cadenas de conexión ni credenciales |

**Criterio de salida:** interoperabilidad segura sin acceso directo.

---

### Lote 9 — Experiencia de usuario

| # | Tarea | Verificación |
|---|---|---|
| 9.1 | Cliente API tipado desde OpenAPI | `tsc --noEmit` sin errores |
| 9.2 | Login, layout, menú por permisos | Usuario sin permiso no ve opción |
| 9.3 | Pantalla de requisiciones | Playwright crea y envía requisición sintética |
| 9.4 | Pantalla de autorizaciones | Playwright aprueba y rechaza |
| 9.5 | Pantalla de almacén | Playwright reserva y entrega |
| 9.6 | Pantallas de compras/equipos/costos | Pruebas E2E de flujo crítico |
| 9.7 | Accesibilidad y mensajes de error | auditoría básica y textos claros |

**Criterio de salida:** flujos críticos cubiertos por Playwright en `127.0.0.1`.

---

### Lote 10 — Endurecimiento para intranet

**No ejecutar sin autorización formal.**

Incluiría TLS interno, proxy inverso, políticas de firewall, respaldo, monitoreo, SSO y plan de migración oficial. Requiere aprobación de infraestructura y seguridad.

---

## 4. Definición de preparado y terminado

### Preparado

- La tarea está en el lote activo.
- Existe documento de contrato o modelo aprobado.
- No depende de una decisión pendiente del negocio.
- El entorno local es suficiente para probarla.

### Terminado

- Código, migración y pruebas en el mismo cambio.
- Todas las pruebas pasan localmente.
- Sin secretos ni datos reales.
- Bitácora cubre acciones sensibles.
- Documentación actualizada si cambió contrato/esquema/decisión.
- Se reporta qué no quedó incluido.

---

## 5. Registro de riesgos

| ID | Riesgo | Prob. | Impacto | Señal de alerta | Mitigación | Responsable |
|---|---|---|---|---|---|---|
| R-01 | Se interprete el ERP como segundo inventario oficial | Media | Alto | Usuario intenta “ajustar” stock de CONTPAQi desde ERP | `external_system.official_inventory`, snapshots, conciliación y cartel de “operativo” en UI | Arquitectura/Operación |
| R-02 | Intento de conexión directa a CONTPAQi | Baja | Alto | Cadena de conexión o driver en repo | Prohibición en AGENTS; revisión de dependencias y diffs | DevOps |
| R-03 | Escritura accidental en Sierra Madre GMAO | Baja | Alto | Credenciales de GMAO o endpoints de escritura | Solo IDs externos y eventos locales; sin credenciales | Integraciones |
| R-04 | Sobre-reserva por concurrencia | Media | Alto | Dos entregas simultáneas del mismo lote | `FOR UPDATE`, idempotencia, prueba de carrera | Backend |
| R-05 | Doble contabilización por reintentos | Media | Alto | Misma OC/factura procesada dos veces | `idempotency_key`, inbox/outbox, Unique constraints | Backend/Finanzas |
| R-06 | Datos reales en semillas o capturas | Media | Alto | Nombres/proveedores reales en fixtures | Datos `DEMO_*`, revisión de PR, escáner de secretos | Todo el equipo |
| R-07 | Permisos excesivos | Media | Alto | Almacenista puede aprobar compras | RBAC por acción y alcance; pruebas de negación | Seguridad |
| R-08 | Migración destructiva | Baja | Alto | `DROP`, `TRUNCATE`, `DELETE` en Alembic | Política aditiva y revisión obligatoria | DBA |
| R-09 | Pérdida de trazabilidad por IDs internos opacos | Media | Medio | No existe número de documento legible | `doc.document_registry` y eventos | Backend |
| R-10 | Confusión entre recibido y entregado | Media | Medio | Reporte iguala ambos conceptos | Vista de cantidades y UI con columnas separadas | Producto |
| R-11 | Zona horaria de turnos subterráneos | Media | Medio | Horas duplicadas en cambio de horario | `TIMESTAMPTZ` y presentación fija | Backend/UI |
| R-12 | Credenciales en repositorio | Baja | Alto | `.env` versionado o token en código | `.gitignore`, `.env.example` vacío, escáner | DevOps |
| R-13 | Alcance excesivo del proyecto | Alta | Medio | Lote con más de 10 tareas | Divisiones y criterios de salida | Producto |
| R-14 | Dependencia de CONTPAQi para operar | Media | Medio | Proceso detenido si no hay exportación | Modo operativo local y reconciliación diferida | Operación |
| R-15 | Reportes lentos con Many almacenes | Baja | Medio | Consultas sin índice en movimientos | Índices desde Lote 1/4 y explain básico | Backend |
| R-16 | Falta de evidencia para auditoría | Media | Alto | Acción sensible sin `audit_log` | Middleware + servicio en misma transacción | Seguridad |
| R-17 | Exposición accidental de red | Baja | Alto | `--host 0.0.0.0` o puerto publicado | Comandos fijos en docs y revisión | DevOps |
| R-18 | Cambio de reglas fiscales | Media | Alto | ERP intenta calcular impuestos oficiales | CONTPAQi sigue como oficial; ERP solo referencia | Finanzas |

---

## 6. Puertas de calidad entre lotes

| Puerta | Pregunta que debe responderse sí |
|---|---|
| Seguridad | ¿RBAC y bitácora cubren lo nuevo? |
| Datos | ¿La migración es aditiva y probada desde cero? |
| Concurrencia | ¿Existen pruebas de carrera sobre saldos/cantidades? |
| Trazabilidad | ¿Cada documento tiene número, evento y actor? |
| Integración | ¿No se abrió conexión a sistemas externos? |
| Pruebas | ¿Pasaron Pytest y, si aplica, Playwright? |
| Secretos | ¿El diff no contiene credenciales ni datos reales? |
| Documentación | ¿Contratos y modelos siguen coincidiendo con el código? |

---

## 7. Cómo reportar avance

Formato sugerido para cada lote:

```text
Lote: 1 — Cimientos técnicos
Estado: terminado / parcial / bloqueado
Cambios: ...
Pruebas ejecutadas: pytest -q (NN passed), npm run build OK, alembic upgrade head OK
Migraciones: 0001_initial (aditiva)
Riesgos detectados: ...
Pendiente para siguiente lote: ...
Evidencia de localidad: uvicorn --host 127.0.0.1; sin puertos publicados
```

Nunca reemplazar “terminado” por “casi”, “debería funcionar” o “compila”.
