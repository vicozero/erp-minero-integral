# Auditoría de código — ERP MINERO INTEGRAL

**Fecha:** 2026-11-18  
**Alcance:** revisión estática del código existente en `E:\ERP_MINERO` (backend FastAPI/SQLAlchemy, migraciones Alembic, semilla, pruebas y frontend React/TypeScript).  
**Restricción cumplida:** no se modificó ningún archivo de código, configuración, prueba, migración ni documento existente. El único archivo creado es este informe.

> **Importante sobre ejecución:** durante esta auditoría **no se ejecutaron pruebas ni compilaciones**. Más adelante se citan, de forma explícita, los resultados que ya constaban en la conversación previa a esta revisión. No se afirma aquí ninguna verificación nueva.

## 1. Resumen ejecutivo

| Severidad | Cantidad | Temas principales |
|---|---:|---|
| CRÍTICO | 2 | RBAC sin alcance/propiedad; idempotencia regenerada en el cliente que permite movimientos duplicados |
| ALTO | 8 | Carreras de idempotencia, reservas vencidas que bloquean stock, validación multiempresa, migración `create_all`, fechas sin `TIMESTAMPTZ`, auditoría no inmutable, secretos/login, falta de validación PostgreSQL/concurrencia |
| MEDIO | 8 | Invariantes solo en servicio, aprobación incompleta, OC canceladas en faltantes, numeración, errores 500, cliente API, costos, catálogos globales |
| BAJO | 8 | Configuración relativa, hash de IP, límites de auditoría, `.gitignore`, documentación, checks de BD, CORS, edición de borrador |

**Conclusión general:** la estructura modular y la separación de dominios son coherentes con `AGENTS.md`, y no se encontraron inyecciones SQL. Sin embargo, la primera versión **no es segura para multiusuario real** (permisos globales) ni **confiable para concurrencia** (idempotencia de cliente y carreras en el servidor). La prueba de concurrencia está omitida y no existe validación contra PostgreSQL.

---

## 2. Hallazgos CRÍTICOS

### C-01 — RBAC sin alcance, sin control de propiedad y sin validación del rol del paso de aprobación

- **Área evaluada:** 4 (Seguridad de autenticación y permisos).
- **Archivos y ubicación:**
  - `backend/app/api/v1/deps.py`, líneas 28-40 (`require_permission`).
  - `backend/app/modules/identity/service.py`, líneas 60-89 (`IdentityService.has_permission`).
  - `backend/app/api/v1/routers/requisitions.py`, líneas 34-40 (`list_all`), 43-52 (`get_one`), 55-64 (`update_draft`), 78-87 (`decide`).
  - `backend/app/modules/requisitions/service.py`, líneas 175-180 (paso con `role_code="APROBADOR"`) y 196-322 (`decide`).
  - `backend/app/modules/identity/models.py`, líneas 53-65 (`UserRole.scope_type`, `scope_id`, `valid_from`, `valid_to`).
- **Impacto:** `require_permission` solo comprueba el código del permiso. Las columnas de alcance (`company_id`, `mining_unit_id`, `department_id`, `warehouse_id`) definidas en el modelo `UserRole` **se ignoran**. Cualquier usuario con `requisition.view` lista y lee todas las requisiciones de todas las unidades; cualquier usuario con `requisition.create` puede modificar el borrador de otro usuario (`update_draft` no verifica `requester_id`). Además, `ApprovalStep.role_code` nunca se contrasta con los roles del actor: basta tener `requisition.approve` para decidir. Esto contradice `AGENTS.md` §8 (“RBAC con permisos granulares… alcance opcional por company/mining_unit/department/warehouse”) y habilita acceso y modificación no autorizados en un ERP multiusuario.
- **Corrección recomendada:**
  1. Extender `require_permission` para resolver el alcance efectivo del usuario desde `UserRole` (incluyendo `valid_to`) y pasarlo como dependencia explícita al servicio.
  2. Aplicar filtros obligatorios por `company_id`/`mining_unit_id`/`department_id`/`warehouse_id` en `list_all`, `get_one`, catálogos, kardex y bitácora.
  3. Verificar propiedad en `update_draft` y `submit` (`req.requester_id == actor_id`, salvo ADMIN con alcance).
  4. En `decide`, comprobar que el actor posee el `role_code` del `ApprovalStep` vigente y registrarlo en la decisión.
  5. Agregar pruebas de 403/404 para cruces de unidad, departamento, almacén y propiedad.

### C-02 — Claves de idempotencia generadas en cada clic: duplicación real de reservas, entregas y recepciones

- **Área evaluada:** 7 (Riesgos de duplicar requisiciones, compras o movimientos).
- **Archivos y ubicación:**
  - `frontend/src/features/inventory/Inventory.tsx`, líneas 13-15 (`newKey`), 71-84 (`action('reserve')` y `action('issue')` crean `newKey('res')` / `newKey('iss')` en cada envío).
  - `frontend/src/features/purchases/Purchases.tsx`, líneas 14-16 (`newKey`), 89-105 (`receiveOrder` crea `newKey('grn')` en cada envío).
- **Impacto:** la clave de idempotencia se genera **dentro del manejador de la acción**, no cuando nace la intención del usuario. Un doble clic, un reintento tras error de red o una recarga produce claves distintas; el backend las acepta como operaciones nuevas y descuenta el stock dos veces, genera dos movimientos de kardex o dos recepciones. Las restricciones `UNIQUE(idempotency_key)` de la base no protegen porque las claves son diferentes. Es el riesgo de duplicidad más probable del sistema, justamente en movimientos que afectan existencias.
- **Corrección recomendada:**
  1. Generar `idempotency_key` una sola vez por intención (al abrir el formulario o al entrar en modo edición), guardarla en estado del componente y reutilizarla hasta que la operación termine o se cancele explícitamente.
  2. Deshabilitar los botones mientras `loading` esté activo y limpiar la clave solo tras éxito confirmado.
  3. Envíar la clave también como cabecera `Idempotency-Key` y exigirla en los endpoints POST que mutan stock (no opcional).
  4. Agregar pruebas de front-end que simulen doble envío y verifiquen una sola petición con la misma clave, además de pruebas backend de reintento con la misma clave.

---

## 3. Hallazgos ALTOS

### A-01 — Idempotencia del servidor no atómica: patrón SELECT-then-INSERT sin manejo de colisión

- **Área evaluada:** 6 (Transacciones y concurrencia) y 7 (Duplicados).
- **Archivos y ubicación:**
  - `backend/app/modules/inventory/service.py`, líneas 110-115 (`reserve`), 193-198 (`issue`), 310-314 (`receive_stock`).
  - `backend/app/modules/purchasing/service.py`, líneas 169-173 (`receive`).
- **Impacto:** se busca la clave con `SELECT`, y si no existe se inserta. Dos peticiones concurrentes con la **misma** clave superan ambas el `SELECT`; una inserta y la otra viola el `UNIQUE` (`uq_reservation_idem`, `uq_movement_idem`, `uq_grn_idem`). No hay `except IntegrityError`, `SAVEPOINT` ni `INSERT ... ON CONFLICT ... RETURNING`, por lo que la segunda petición termina en HTTP 500 y deja bloqueos/estado parcial hasta el rollback de la sesión. Adicionalmente, `PurchasingService.receive` devuelve la recepción existente sin verificar que pertenezca al `purchase_order_id` solicitado, y `reserve` usa una clave derivada `reserve:{line}:{quantity}` que fusiona reservas legítimas de igual monto.
- **Corrección recomendada:** usar inserción atómica con `ON CONFLICT (idempotency_key) DO NOTHING RETURNING id` (o capturar `IntegrityError` dentro de `begin_nested()`, hacer rollback del savepoint y releer la fila), validar que la entidad recuperada pertenezca al documento destino, y eliminar la clave derivada por contenido. Cubrir con pruebas de dos hilos/transacciones reales sobre PostgreSQL.

### A-02 — Las reservas vencidas nunca liberan `reserved_qty`

- **Área evaluada:** 6 (Transacciones/concurrencia) y 8 (Inventario y cantidades).
- **Archivos y ubicación:**
  - `backend/app/modules/inventory/service.py`, líneas 83-90 (`line_reserved_qty` filtra `expires_at > now`), 136-162 (`reserve` incrementa `balance.reserved_qty`), 211-242 (`issue` decrementa solo la reserva consumida).
  - `backend/app/shared/constants.py`, línea 59 (`RESERVATION_STATUSES` incluye `EXPIRED`, pero ningún código lo asigna).
  - `backend/app/modules/inventory/models.py`, líneas 34-57.
- **Impacto:** cuando expira una reserva (`expires_at = now + 7 días`, línea 158), deja de contar para la partida pero **sigue restando existencia disponible** en `StockBalance`. No hay job, endpoint ni lógica que cambie su estado a `EXPIRED` y devuelva `reserved_qty`. El almacén pierde stock disponible de forma permanente hasta una corrección manual; las consultas de disponibilidad y las decisiones de compra por faltantes quedan sesgadas.
- **Corrección recomendada:** implementar una operación transaccional `expire_reservations(db, now)` que bloquee las reservas `ACTIVE` vencidas (`FOR UPDATE`), decrement `balance.reserved_qty`, marque `status='EXPIRED'`, registre auditoría y evento documental; invocarla antes de `reserve`, `issue`, `availability` y `create_from_shortages` (y programarla periódicamente). Agregar prueba con `expires_at` manipulado que verifique la recuperación de `available_qty`.

### A-03 — Integridad multiempresa/multiunidad no validada y unidad demo codificada

- **Área evaluada:** 1 (Arquitectura/coherencia) y 3 (Integridad referencial).
- **Archivos y ubicación:**
  - `backend/app/modules/requisitions/service.py`, líneas 36-55 (solo valida existencia por ID), 43-45 (unidad `"LAG_DEMO"` fija), 64-80 (`department_id`, `warehouse_id`, `equipment_id`, `cost_center_id` asignados sin control de compañía).
  - `backend/app/modules/purchasing/service.py`, líneas 67-70 (proveedor y almacén cualquiera por ID), 93-99 (OC toma compañía de la requisición, pero almacén puede ser de otra).
  - `backend/app/modules/master_data/models.py`, líneas 21-41 y `backend/app/modules/organization/models.py`, líneas 56-74.
- **Impacto:** es posible crear requisiciones que mezclan departamento, almacén, centro de costo, artículo y equipo de compañías o unidades distintas; `equipment_id` ni siquiera se valida (FK inválida → error 500 en lugar de 404). La unidad minera está escrita en código, por lo que la promesa de “múltiples unidades mineras” de `AGENTS.md` §2 no es operativa. El inventario operativo queda expuesto a contaminación entre unidades.
- **Corrección recomendada:** derivar `company_id`/`mining_unit_id` del usuario y del almacén autorizado (no de una constante), validar para cada entidad referenciada que `company_id` y `mining_unit_id` sean coherentes con el documento, validar explícitamente `equipment_id`, y devolver 422/404 con mensaje accionable. Agregar pruebas de rechazo de referencias cruzadas.

### A-04 — Migración inicial usa `create_all` y permite downgrade destructivo sin comprobar base vacía

- **Área evaluada:** 3 (Integridad referencial y migraciones).
- **Archivos y ubicación:**
  - `backend/migrations/versions/0001_initial_schema.py`, líneas 56-62 (`Base.metadata.create_all(checkfirst=True)`) y 65-76 (`downgrade` con `DropSchema(..., cascade=True)`).
  - `backend/migrations/env.py`, líneas 44-51.
- **Impacto:** Alembic queda reducido a un `create_all`: si una tabla ya existe, `upgrade` no agrega columnas, check constraints ni índices nuevos; el historial de revisiones no representa cambios reales de esquema. El mensaje del `downgrade` afirma que solo se permite “en base vacía”, pero el código **únicamente** comprueba `ALLOW_DESTRUCTIVE_DOWNGRADE=1` y ejecuta `DROP TABLE`/`DROP SCHEMA CASCADE`. Una variable de entorno mal puesta puede destruir datos, en contra de `AGENTS.md` §3.6 y §4. Tampoco hay evidencia de prueba `empty → head`.
- **Corrección recomendada:** generar DDL versionado con `op.create_table`/`op.create_schema` (o `alembic revision --autogenerate` revisado) en lugar de `create_all`; eliminar o endurecer el `downgrade` (verificar conteo de filas y esquema vacío, exigir confirmación interactiva y ticket). Agregar prueba automatizada de migración `empty → head` contra PostgreSQL efímero y verificar constraints con consultas a `information_schema`.

### A-05 — Fechas mapeadas sin zona horaria: PostgreSQL crea `timestamp without time zone`

- **Área evaluada:** 1 (Coherencia PostgreSQL) y 9 (Auditoría).
- **Archivos y ubicación:**
  - `backend/app/db/base.py`, líneas 25-40 (`AuditMixin.created_at`, `occurred_at`, `ImmutableMixin.occurred_at`).
  - Todos los modelos con `Mapped[datetime]`: `identity/models.py` 27, 64-65, 88; `requisitions/models.py` 54-59; `inventory/models.py` 56, 98; `purchasing/models.py` 39, 89; `documentation/models.py` 63, 84; `audit/models.py` 20; `integrations/models.py` 36-37, etc.
- **Impacto:** SQLAlchemy infiere `DateTime()` sin `timezone=True`, que en PostgreSQL es `TIMESTAMP WITHOUT TIME ZONE`, mientras el código asigna `datetime.now(timezone.utc)` (p. ej. `requisitions/service.py` 162, `identity/service.py` 38, `inventory/service.py` 88). El offset se pierde al persistir; el ordenamiento de `occurred_at`, la vigencia de reservas y la auditoría pueden interpretarse en otra zona. Incumple `AGENTS.md` §6 (“Timestamps `TIMESTAMPTZ`; zona de referencia `America/Mexico_City`”).
- **Corrección recomendada:** definir un tipo compartido `DateTime(timezone=True)` y usarlo de forma explícita en todas las columnas de fecha (o `Mapped[datetime]` con `mapped_column(DateTime(timezone=True))`), incluidas `server_default=func.now()` donde aplique. Crear migración aditiva con `ALTER COLUMN ... TYPE TIMESTAMPTZ USING ... AT TIME ZONE 'America/Mexico_City'` y verificar el tipo en `information_schema.columns`.

### A-06 — Bitácora y eventos no son append-only y no registran correlación

- **Área evaluada:** 9 (Registro de auditoría).
- **Archivos y ubicación:**
  - `backend/app/modules/audit/models.py`, líneas 12-33 (`correlation_id` existe pero nadie lo llena; `action` sin CHECK).
  - `backend/app/modules/audit/service.py`, líneas 34-63 (`record` nunca recibe `ip_hash` salvo en login; no hay `flush` ni control de inmutabilidad).
  - `backend/migrations/versions/0001_initial_schema.py`, líneas 56-62 (no crea reglas, triggers ni permisos).
  - `backend/app/modules/inventory/models.py`, líneas 60-101 (`stock_movement.status` sin CHECK y sin prevención de `UPDATE`/`DELETE`).
- **Impacto:** `aud.audit_log`, `doc.document_event` e `inv.stock_movement` pueden ser modificados o borrados por cualquier código ORM con acceso a la sesión; no hay trigger `BEFORE UPDATE OR DELETE`, ni `REVOKE` de DML. La bitácora no incluye `correlation_id` y la mayoría de las acciones omiten `ip_hash`. Esto contradice los principios de “append-only para hechos contables y de inventario” y “bitácora registra actor, acción, entidad, antes/después, request_id y correlación” (`AGENTS.md` §3.5 y §8).
- **Corrección recomendada:** crear reglas/triggers que bloqueen `UPDATE`/`DELETE` en tablas inmutables y revocar esos permisos al usuario de aplicación; llenar `correlation_id` desde la cabecera `X-Correlation-ID` (con fallback a `X-Request-ID`) en el middleware; propagar `ip_hash` en todas las operaciones sensibles; exigir `flush()` de la auditoría dentro de la misma transacción del cambio de negocio. Agregar prueba de que un `UPDATE`/`DELETE` directo falla.

### A-07 — Secretos y autenticación insuficientemente endurecidos

- **Área evaluada:** 4 (Seguridad).
- **Archivos y ubicación:**
  - `backend/app/core/config.py`, líneas 20-22 (`DATABASE_URL` y `SECRET_KEY` requeridos pero sin validación de contenido).
  - `.env.example`, líneas 10 y 13 (`DATABASE_URL=` y `SECRET_KEY=` vacíos).
  - `backend/app/core/security.py`, líneas 34-58 (JWT HS256 sin `iss`/`aud`/`jti` ni denylist).
  - `backend/app/api/v1/routers/auth.py`, líneas 16-28 (login sin límite de intentos ni bloqueo).
  - `backend/app/modules/identity/service.py`, líneas 16-58 (`LoginAudit` registra fallos, pero `status='LOCKED'` nunca se asigna).
- **Impacto:** una cadena vacía o trivial en `SECRET_KEY` es aceptada por Pydantic: copiar `.env.example` sin completarlo produce tokens firmados con secreto vacío. No hay rate limiting, backoff ni bloqueo tras fallos repetidos, aunque el modelo contempla `LOCKED`. El logout del frontend solo descarta el token en memoria; no hay revocación. En intranet multiusuario esto facilita fuerza bruta y suplantación.
- **Corrección recomendada:** validar `SECRET_KEY` con longitud mínima (≥32 bytes) y entropía, y `DATABASE_URL` con esquema permitido; dejar `.env.example` con placeholders no válidos que obliguen a editarlo; agregar contador de fallos por usuario/IP con bloqueo temporal y auditoría; considerar `jti` + denylist o reducción del TTL; documentar rotación de secreto. Cubrir con pruebas de rechazo de secreto débil y de bloqueo tras N intentos.

### A-08 — Sin validación contra PostgreSQL ni pruebas de concurrencia; cobertura crítica ausente

- **Área evaluada:** 10 (Pruebas ejecutadas y cobertura faltante).
- **Archivos y ubicación:**
  - `backend/tests/test_concurrency.py`, líneas 14-40 (prueba omitida con `@pytest.mark.skip`).
  - `backend/tests/conftest.py`, líneas 51-83 (SQLite en memoria, `StaticPool`, override de sesión compartida).
  - `README.md`, líneas 111-117 y 133-138.
- **Impacto:** toda la lógica de `SELECT ... FOR UPDATE`, bloqueos de fila en numeración, `READ COMMITTED`/`SERIALIZABLE`, constraints de PostgreSQL y migraciones se ejecuta sobre SQLite, que no las implementa igual. La única prueba de concurrencia está omitida. No hay prueba de `alembic upgrade head`, ni de fallo/reintento transaccional, ni de permisos por alcance. Un fallo de concurrencia o de esquema no se detectaría antes de desplegar.
- **Corrección recomendada:** crear un perfil de pruebas con PostgreSQL efímero (contenedor o instancia local en `127.0.0.1`), desomitir y fortalecer `test_folios_concurrentes_son_unicos`, agregar pruebas de idempotencia concurrente, de expiración de reservas, de RBAC con alcance y de migración `empty → head`. Mantener SQLite solo como batería rápida de dominio y documentar la diferencia.

---

## 4. Hallazgos MEDIOS

### M-01 — Invariantes de cantidad solo encapsulados en servicio; `pending_qty` incorrecto

- **Archivo/ubicación:** `backend/app/modules/requisitions/models.py` 66-75; `backend/app/modules/requisitions/service.py` 348; `backend/app/modules/requisitions/schemas.py` 22; `backend/app/modules/inventory/models.py` 18-24; `backend/app/modules/organization/models.py` 74.
- **Impacto:** los CHECK de BD garantizan `>= 0`, pero no `authorised_qty <= requested_qty - cancelled_qty`, `reserved_qty <= authorised_qty - delivered_qty` ni `received_qty <= ordered_qty`. `Decimal` no tiene `max_digits`/`decimal_places`, por lo que un valor mayor a `NUMERIC(18,6)` provoca error 500. `pending_qty` se calcula como `requested - cancelled - delivered`, no como `authorised - delivered`, mostrando pendiente por encima de lo autorizado. `Warehouse.allows_negative` existe pero se ignora.
- **Corrección:** agregar CHECK constraints a nivel de tabla, limitar los decimales en Pydantic, corregir `pending_qty` a `authorised_qty - delivered_qty` y respetar `allows_negative` en la validación de saldos.

### M-02 — Decisión de aprobación incompleta y segregación de funciones ausente

- **Archivo/ubicación:** `backend/app/modules/requisitions/service.py` 224-322; `backend/app/modules/purchasing/service.py` 143-165.
- **Impacto:** las partidas no incluidas en `payload.decisions` quedan con `authorised_qty = 0` y `status='OPEN'` aunque la requisición pase a `PARTIALLY_APPROVED`; no se exige decisión para todas las líneas. `PurchasingService.approve` permite que el mismo `buyer_id` que creó la OC la apruebe si tiene ambos permisos.
- **Corrección:** exigir cobertura de todas las partidas abiertas (o cancelar explícitamente las omitidas), validar `step.role_code` y registrar quién decide; impedir autoaprobación de OC o exigir aprobador distinto.

### M-03 — Faltantes de compra incluyen órdenes canceladas

- **Archivo/ubicación:** `backend/app/modules/purchasing/service.py` 40-46 (`line_purchased_qty` suma todas las líneas sin filtrar `PurchaseOrder.status`).
- **Impacto:** una OC en estado `CANCELLED`/`CLOSED` sigue descontando del faltante; el comprador no puede generar una nueva OC y la requisición queda bloqueada.
- **Corrección:** filtrar por estados vigentes (`DRAFT`, `APPROVED`, `SENT`, `PARTIALLY_RECEIVED`) y exponer `cancelled_qty` ya descontado; agregar prueba con OC cancelada.

### M-04 — Numeración con collisiones no controladas y año inconsistente

- **Archivo/ubicación:** `backend/app/shared/numbering.py` 17-23 y 70; `backend/app/modules/documentation/models.py` 23-31; `backend/app/db/seed.py` 255-273.
- **Impacto:** `_get_or_create_type` no maneja `IntegrityError` si dos transacciones crean el mismo `DocumentType` (colisión → 500). El año se toma de UTC en `next_document_number` pero de `datetime.now()` local en la semilla, con posible desalineación enero/diciembre respecto a `TIMEZONE`. La restricción única con `mining_unit_id` nullable permite varias filas con NULL en PostgreSQL.
- **Corrección:** usar `ON CONFLICT DO NOTHING RETURNING` para tipos/numeraciones, centralizar el cálculo del año en la zona configurada y usar un índice único funcional (`COALESCE(mining_unit_id, uuid_nil)`).

### M-05 — Errores de integridad no se traducen a respuestas 4xx

- **Archivo/ubicación:** todos los routers (`requisitions.py`, `inventory.py`, `purchasing.py`, `auth.py`) y `backend/app/main.py` 12-42 (sin manejadores de excepción).
- **Impacto:** FK inexistente (`equipment_id`, ver A-03), violación de CHECK o `IntegrityError` por carrera generan HTTP 500 con traza, sin rollback explícito ni mensaje accionable; el frontend muestra `Error 500`.
- **Corrección:** registrar manejadores globales para `IntegrityError`/`SQLAlchemyError` → 409/422 con detalle seguro, manteniendo 500 solo para errores no esperados y sin exponer SQL ni secretos.

### M-06 — Cliente API sin recuperación de sesión y flujo create+submit no atómico

- **Archivo/ubicación:** `frontend/src/api/client.ts` 32-53; `frontend/src/features/requisitions/Requisitions.tsx` 71-110.
- **Impacto:** un 401 (token expirado) se muestra como error textual y no fuerza reautenticación. “Guardar y enviar” ejecuta dos POST independientes: si falla el `submit`, queda un borrador huérfano sin reintento identificable.
- **Corrección:** interceptar 401 en `request` y limpiar sesión/redirigir a `/login`; agregar endpoint compuesto o clave de idempotencia compartida para create+submit, y ofrecer reintento del envío.

### M-07 — Capas de costo y reversales incompletas

- **Archivo/ubicación:** `backend/app/modules/costing/models.py` 31-46; `backend/app/modules/inventory/service.py` 188-293; `backend/app/shared/constants.py` 57.
- **Impacto:** `CostLayer.remaining_qty` se crea en recepción pero nunca se consume en las entregas (`ISSUE`), por lo que la valuación no sigue al stock. Existen tipos `ADJUSTMENT_*`, `RETURN` y `REVERSAL` en constantes sin servicios que los generen; las correcciones no son contrapartidas trazables como exige `AGENTS.md` §3.5.
- **Corrección:** implementar consumo de capas (FIFO o política acordada) en `issue`, reversiones con `reversal_of_id` y ajustes autorizados con auditoría, o documentar explícitamente que están fuera del alcance de la versión 0.1.

### M-08 — Catálogos y listados sin filtrado por compañía/unidad

- **Archivo/ubicación:** `backend/app/api/v1/routers/catalogs.py` 17-47; `backend/app/api/v1/routers/inventory.py` 53-77; `backend/app/api/v1/routers/audit.py` 14-33.
- **Impacto:** `rows()` consulta todas las filas de cada modelo sin filtro de compañía; kardex, reservas y bitácora tampoco acotan por unidad. Agrava C-01 y facilita la fuga de información entre unidades mineras.
- **Corrección:** aplicar el alcance resuelto en C-01 a todas las consultas de lectura y paginar/limitar los resultados.

---

## 5. Hallazgos BAJOS

| ID | Archivo / ubicación | Impacto | Corrección recomendada |
|---|---|---|---|
| B-01 | `backend/app/core/config.py` 7-12 | `env_file="../.env"` depende del directorio de trabajo; ejecutar desde la raíz no carga `.env`. | Resolver la ruta con `Path(__file__).resolve().parents[2] / ".env"`. |
| B-02 | `backend/app/modules/audit/service.py` 28-31 | `hash_ip` usa SHA-256 sin sal; IPs son de baja entropía y revertibles por diccionario. | Usar HMAC con clave de aplicación o sal por instalación. |
| B-03 | `backend/app/api/v1/routers/audit.py` 16 | `limit` sin `ge`/`le`; valores negativos o enormes afectan la respuesta. | `Query(100, ge=1, le=1000)` y paginación. |
| B-04 | `.gitignore` 26 | `*.sql` ignora posibles archivos SQL de migración futuros. | Restrictir el patrón a `exports/`, `*.dump`, `*.backup`. |
| B-05 | `README.md` 117; `frontend/src/features/dashboard/Dashboard.tsx` 49-52 | README afirma que las pruebas PostgreSQL “se omiten automáticamente” (solo hay una omitida explícitamente); el dashboard muestra “—” en OC. | Corregir documentación y consultar `api.purchases().length`. |
| B-06 | `backend/app/modules/inventory/models.py` 45, 97 | `reservation_no` sin UNIQUE y `status` sin CHECK; estados inválidos pueden persistirse. | Agregar `UniqueConstraint("reservation_no")` y CHECK de estado. |
| B-07 | `backend/app/main.py` 18-24 | CORS con `allow_methods=["*"]`, `allow_headers=["*"]` y credenciales; orígenes están restringidos a loopback, pero conviene minimizar. | Enumerar métodos y cabeceras necesarios. |
| B-08 | `backend/app/modules/requisitions/service.py` 114-144; `schemas.py` 11-15 | `update_draft` no permite corregir partidas de un borrador. | Definir contrato de edición de líneas o documentar la limitación. |

---

## 6. Evaluación por las diez áreas solicitadas

| # | Área | Resultado |
|---:|---|---|
| 1 | Arquitectura y coherencia frontend/backend/PostgreSQL | **Parcial.** Monolito modular coherente y contratos TypeScript alineados con los esquemas Pydantic. Fallan la multiunidad real (A-03), los tipos de fecha (A-05) y el pipeline de migraciones (A-04). |
| 2 | Errores de programación y código incompleto | **Presentes.** Unidad hardcodeada, `equipment_id` sin validar, `pending_qty` incorrecto, costos/reversales y edición de partidas incompletos (A-03, M-01, M-07, B-08). |
| 3 | Integridad referencial y migraciones | **Débil.** FKs correctas en los modelos, pero sin validación de compañía, CHECK de invariantes insuficientes y migración basada en `create_all` con downgrade destructivo (A-03, A-04, M-01). |
| 4 | Seguridad de autenticación y permisos | **Crítica.** JWT y bcrypt adecuados, pero RBAC sin alcance ni propiedad, rol de aprobación no verificado, secreto sin validar y login sin límite (C-01, A-07). |
| 5 | Prevención de inyección SQL | **Sin hallazgos.** Todas las consultas usan SQLAlchemy ORM con parámetros enlazados; los CHECK se construyen desde constantes internas (`shared/constants.py`) y no desde entrada del usuario; `op.execute` usa sentencias estáticas. Riesgo residual: bajo. |
| 6 | Transacciones y concurrencia | **No demostrada.** Bloqueos `FOR UPDATE` y numeración con fila bloqueada están implementados, pero la idempotencia es no atómica, la prueba de concurrencia está omitida y nunca se validó en PostgreSQL (A-01, A-08). |
| 7 | Riesgos de duplicar requisiciones, compras o movimientos | **Altos.** Claves de cliente regeneradas (C-02), carreras servidor (A-01) y OC canceladas que distorsionan faltantes (M-03). La creación de requisiciones y OC no expone clave de idempotencia al cliente. |
| 8 | Validación de inventarios y cantidades | **Parcial.** `NUMERIC`, CHECK de no negatividad y control de sobreentrega funcionan en la batería SQLite; faltan invariantes en BD, expiración de reservas y consistencia de `pending_qty` (A-02, M-01). |
| 9 | Registro de auditoría | **Parcial.** Se registran eventos de negocio, login y documentos en la misma transacción, pero no hay inmutabilidad, correlación ni IP en la mayoría de entradas (A-06). |
| 10 | Pruebas ejecutadas y cobertura faltante | **Insuficiente.** Batería rápida razonable para el flujo feliz; sin PostgreSQL, sin concurrencia, sin permisos por alcance y sin prueba de migración (A-08; detalle en §7). |

---

## 7. Pruebas: resultados citados y cobertura faltante

### 7.1 Resultados ya obtenidos en la conversación previa a esta auditoría

Estos resultados **no fueron reejecutados durante la revisión**; se trasladan tal como constan en el registro de la sesión anterior:

- Backend: `python -m pytest -q` → **17 aprobadas, 1 omitida** (`test_folios_concurrentes_son_unicos`).
- Backend: `python -m ruff check app tests migrations --output-format concise` → **sin errores**.
- Backend: `python -m mypy app` → **sin problemas** en 59 archivos fuente.
- Backend: `python -m compileall -q app tests` → correcto.
- Frontend: `npm.cmd run test -- --run` → **1 prueba aprobada**.
- Frontend: `npm.cmd run build` → compilación correcta con Vite 5.4.21.

### 7.2 Cobertura faltante

1. PostgreSQL local: `alembic upgrade head` desde base vacía, verificación de esquemas y tipos (`TIMESTAMPTZ`, CHECK, índices).
2. Concurrencia: folios únicos, idempotencia de reservas/entregas/recepciones con dos transacciones reales.
3. Seguridad: expiración de token, usuario inactivo, intentos fallidos de login, permisos por alcance y propiedad, rol del paso de aprobación.
4. Inventario: expiración de reservas y liberación de `reserved_qty`, sobreentrega concurrente, límites de `NUMERIC(18,6)`.
5. Compras: OC cancelada en cálculo de faltantes, reutilización de `idempotency_key` entre órdenes, doble recepción simultánea.
6. Auditoría: inmutabilidad de tablas, `correlation_id`, presencia de `before/after` e `ip_hash`.
7. Frontend: doble clic/idempotencia, manejo de 401, flujo create+submit con fallo intermedio.
8. Documentación: corregir la afirmación sobre omisión automática de pruebas PostgreSQL en `README.md`.

---

## 8. Instrucción concreta para OpenCode

> **OpenCode: corrige únicamente los hallazgos CRÍTICOS y ALTOS de `docs/AUDITORIA_CODEX.md` (C-01, C-02, A-01, A-02, A-03, A-04, A-05, A-06, A-07 y A-08). No modifiques los hallazgos MEDIOS ni BAJOS en esta pasada, no hagas commit ni push, y no toques CONTPAQi, Sierra Madre GMAO, datos reales ni credenciales.**
>
> Trabaja en lotes pequeños y, para cada lote, agrega o actualiza pruebas y ejecútalas localmente antes de continuar. Criterios de aceptación mínimos:
>
> 1. **C-01:** `require_permission` resuelve alcance; filtros por compañía/unidad/departamento/almacén en requisiciones, catálogos, kardex y auditoría; verificación de `requester_id` y de `ApprovalStep.role_code`; pruebas 403/404 de cruces de alcance.
> 2. **C-02:** clave de idempotencia generada por intención y reutilizada en reintentos; botones deshabilitados durante el envío; prueba de doble envío con una sola operación efectiva.
> 3. **A-01:** inserción atómica o captura de `IntegrityError` con savepoint en `reserve`, `issue`, `receive_stock` y `PurchasingService.receive`; validación de pertenencia de la entidad recuperada; sin claves derivadas por contenido.
> 4. **A-02:** expiración transaccional de reservas con liberación de `balance.reserved_qty`, evento de documento y auditoría; prueba con `expires_at` vencido.
> 5. **A-03:** sin unidad `"LAG_DEMO"` hardcodeada; validación de compañía/unidad de todas las referencias y de `equipment_id`; pruebas de rechazo.
> 6. **A-04:** migración con DDL versionado en lugar de `create_all`; `downgrade` seguro; prueba `empty → head` contra PostgreSQL (omitir y reportar si no hay PostgreSQL disponible, sin afirmar que pasó).
> 7. **A-05:** tipo `DateTime(timezone=True)` compartido en todas las columnas temporales y migración a `TIMESTAMPTZ`.
> 8. **A-06:** triggers/permisos append-only para bitácora, eventos y movimientos; `correlation_id` y `ip_hash` propagados; prueba de rechazo de `UPDATE`/`DELETE`.
> 9. **A-07:** validación de `SECRET_KEY` y `DATABASE_URL`, placeholders no válidos en `.env.example`, bloqueo temporal por fallos de login y auditoría asociada.
> 10. **A-08:** desomitir y ejecutar la prueba de concurrencia con PostgreSQL; agregar pruebas de idempotencia concurrente, alcance RBAC y migración; reportar exactamente qué se ejecutó y qué quedó omitido.
>
> Al finalizar, reporta archivos modificados, comandos ejecutados con sus resultados reales, y cualquier limitación pendiente. No declares “terminado” si falta alguna prueba o migración de esta lista.
