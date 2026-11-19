# Mejora de Requisiciones y Autorizaciones — Resultados

**Fecha:** 19/11/2026  
**Alcance:** frontend y scripts de verificación locales. Sin cambios en backend, esquema de base de datos, migraciones, permisos ni reglas transaccionales.  
**Estado:** verificado en local; no apto para producción sin la revisión pendiente indicada al final.

## 1. Objetivo cumplido

Modernizar las pantallas de **Requisiciones**, **Autorizaciones**, **Historial** y **Dashboard** usando únicamente los endpoints existentes del ERP. La interfaz ahora guía la captura, muestra el estado real por partida, pide confirmación antes de decisiones sensibles y explica qué indicadores no se pueden calcular con el contrato API actual.

No se simuló ningún guardado: todas las acciones invocan los endpoints reales detrás de `http://127.0.0.1:8080`.

## 2. Cambios por pantalla

### Requisiciones (`frontend/src/features/requisitions/Requisitions.tsx`)

- Captura con departamento, almacén, equipo, centro de costo, tipo, prioridad (`LOW`/`NORMAL`/`HIGH`/`URGENT`), fecha requerida, orden de trabajo, justificación y observaciones.
- Buscador de artículos reutilizable (`ItemPicker`) por código, descripción, fabricante, número de parte o código de barras, usando `wmsSearchItems` con filtro de almacén.
- Selección de artículo desde el catálogo WMS sin modificarlo; también se conserva la descripción libre para artículos no catalogados.
- Una sola unidad de medida por partida, con resumen agrupado por UOM para no mezclar piezas, kilogramos ni litros.
- Validación por partida antes de enviar: descripción, unidad y cantidad mayor a cero; la justificación requiere al menos 4 caracteres.
- Guardado de borrador con `POST /requisitions`; edición del mismo borrador con `PATCH /requisitions/{id}/draft`, enviando los `id` de las líneas existentes.
- Confirmación obligatoria antes de enviar a autorización o cancelar; la cancelación exige motivo.
- Adjuntos con SHA-256 y seguimiento con actor, timestamp y metadata resumida.
- Tabla de cantidades derivadas del servidor: solicitada, autorizada, entregada, pendiente y progreso de surtido por partida.

### Autorizaciones (`frontend/src/features/approvals/Approvals.tsx`)

- Bandeja de documentos `SUBMITTED` con contadores de pendientes, partidas y prioridad crítica/alta.
- Filtros por folio/justificación, prioridad y departamento.
- Metadatos del documento: prioridad, estado, departamento, almacén, equipo, centro de costo, fecha requerida, orden de trabajo, observaciones y justificación. El solicitante se marca **«No disponible en la API actual»** en lugar de inventarse un valor.
- UOM resuelto desde catálogos; para cada partida se puede incluir/excluir, editar la cantidad autorizada y capturar motivo.
- Botones: autorizar/rechazar seleccionadas o todo. Todas abren `ConfirmDialog` antes de `POST /decide`.
- Guard de dobles envíos, validación de cantidad dentro de lo solicitado, motivo obligatorio en rechazos y traducción de errores HTTP 401/403/409/422 a mensajes accionables.
- La semántica de decisión es la misma que antes: una línea no seleccionada se envía como `APPROVE` en `0`, y al rechazar una partida las demás se autorizan completas para no cancelar líneas no tocadas por el aprobador.

### Dashboard (`frontend/src/features/dashboard/Dashboard.tsx`)

- KPIs calculados desde la API: requisiciones, pendientes de autorización, autorizadas, órdenes de compra, materiales pendientes y tiempo medio de autorización.
- Flujo de surtido agrupado por UOM, sin sumar unidades incompatibles.
- Botón de actualización manual con timestamp de última lectura; no hay refresco automático que oculte cambios.
- Bloque explícito de **indicadores no disponibles**: monto autorizado, SLA, existencias globales y solicitante por documento.
- Degradación parcial: si falla `purchases`, se muestra el error y el resto de indicadores siguen visibles.

### Historial (`frontend/src/features/history/History.tsx`)

- Línea de tiempo con evento, transición de estado, fecha, actor y metadata.
- Bitácora de auditoría condicionada al permiso `audit.view`; si el rol no la tiene, se muestra un mensaje claro y no se llama al endpoint.
- Filtros de acción y límite, con actor y `request_id` truncados en pantalla (UUID completos permanecen en la base de datos).
- Carga con `Promise.allSettled`: un permiso denegado o un servicio caído no bloquea el historial documental.

### Componentes compartidos y estilos

- `ui.tsx`: `STATUS_LABELS` exportado, `PriorityBadge`, `InlineFieldError`, `ConfirmDialog` y `LineQuantitiesTable`.
- `client.ts`: `describeApiError` y tipado de `ApprovalDecision` / `RequisitionDraftUpdatePayload`.
- `styles.css`: modal accesible, badges de prioridad, resaltado de filas inválidas/seleccionadas y ajustes responsive con soporte de tema claro/oscuro.

## 3. Verificaciones ejecutadas

| Verificación | Resultado |
| --- | --- |
| `cd backend; python -m pytest --disable-warnings` | 68/68 pruebas correctas |
| `cd frontend; npm run test -- --run` | 25/25 pruebas en 8 archivos |
| `cd frontend; npm run build` | correcto (`index-BdcnlC0G.js`, `index-C-fAZDMA.css`) |
| `python scripts/verificar_portal.py` | 30/30 verificaciones del portal |
| `python scripts/verificar_flujo_demo.py` | 11/11 verificaciones del circuito demo |

Circuito demo real ejecutado sobre datos sintéticos: creación → envío → autorización parcial de 4 de 10 y 6 de 6 → estados `PARTIAL` y `AUTHORISED` → historial con `DOCUMENT_NUMBER_ISSUED`, `REQUISITION_CREATED`, `REQUISITION_SUBMITTED` y `REQUISITION_DECIDED`. La ejecución final registrada en evidencia generó `REQ-LAG-2026-000003`; las capturas de DOM usan los documentos sintéticos `000001` y `000002` creados antes.

Evidencia detallada en `docs/EVIDENCIA_REQUISICIONES.md` y archivos de `docs/evidencias_demo/`.

## 4. Seguridad y límites

- No se guardaron contraseñas, tokens ni cadenas de conexión en el repositorio ni en evidencias.
- No se conectó a CONTPAQi ni a Sierra Madre GMAO; la orden de trabajo es solo una referencia textual.
- No se modificaron permisos ni se eludió la validación del servidor: el frontend solo oculta controles y confirma intenciones.
- El portal sigue escuchando en `127.0.0.1:8080` y la API en `127.0.0.1:8000` detrás del proxy; no se abrió LAN, firewall ni TLS.
- No se hicieron migraciones ni operaciones destructivas.

## 5. Limitaciones y siguiente paso

1. Las capturas de pantalla no pudieron generarse: la herramienta de navegador devolvió `UnknownVizError` al interactuar y luego indicó que la pestaña no era visible para capturar. Se conservó evidencia real del DOM en texto.
2. `erp_minero_pilot` no existe; no se ejecutó Alembic `empty -> head` sobre una base de prueba autorizada.
3. La normalización de CHECK con doble prefijo sigue requiriendo aprobación por riesgo sobre datos existentes.
4. El solicitante por documento no está expuesto en el contrato actual de requisiciones; se muestra como no disponible.
5. Para una demostración comercial se recomienda primero formalizar el esquema `wms`, la jerarquía de ubicaciones, lotes/series y las reglas de triple match; después repetir la revisión visual con capturas en un entorno donde el navegador pueda tomarlas.

**No se afirma que el sistema sea apto para producción.** Esta entrega es una mejora local demostrable sobre datos sintéticos.
