# Semáforo de requisiciones — Lote 5

**Fecha:** 19/11/2026
**Estado:** tablero implementado, calculado en backend y validado en el portal.
**Contrato previo:** `docs/SLA_SEMAFORO.md`. Este documento complementa la operación del tablero.

## 1. Principio

El semáforo es un **indicador derivado**, no un estado administrativo. Se muestra en un chip separado, con etiqueta textual accesible, y nunca bloquea aprobaciones ni genera movimientos.

Base temporal: `submitted_at`, con respaldo `created_at` cuando la requisición aún no se envía.

## 2. Umbrales aprobados

| Prioridad | Verde | Amarillo | Rojo |
|---|---:|---:|---:|
| `LOW` | ≤ 72 h | ≤ 96 h | > 96 h |
| `NORMAL` | ≤ 48 h | ≤ 72 h | > 72 h |
| `HIGH` | ≤ 24 h | ≤ 48 h | > 48 h |
| `URGENT` | ≤ 8 h | ≤ 16 h | > 16 h |

La emergencia (4/8 h) permanece **desactivada** salvo aprobación explícita con `sla.policy.approve`. El cálculo usa horas de reloj, no horas hábiles de `America/Mexico_City`.

## 3. Columnas del tablero

| Columna | Origen |
|---|---|
| Folio | `document_no` |
| Departamento | catálogo `org` |
| Equipo | `equipment` resuelto desde `equipment_id` |
| Responsable | solicitante resuelto desde `requester_id` |
| Estado administrativo | estado de la requisición, con badge propio |
| Semáforo | `SlaResult` calculado por backend |
| Fecha requerida | `needed_at` |
| Días pendientes | cálculo del servicio |
| % surtido | entregas respecto de lo autorizado |
| Acciones | enlace a `/trazabilidad/:id` si el perfil tiene `requisition.history.view` |

Los totales superiores muestran VERDE, AMARILLO, ROJO y Sin medición.

## 4. Filtros

El tablero envía al backend los filtros `sla_color`, `status`, `priority`, `department_id`, `equipment_id`, `requester_id`, `date_from` y `date_to`. El botón «Limpiar filtros» restaura todos. El color se calcula siempre en backend; el frontend no decide plazos.

## 5. API

| Método | Ruta | Permiso |
|---|---|---|
| `GET` | `/api/v1/sla/requisitions` | `sla.view` |
| `GET` | `/api/v1/sla/history?requisition_id=` | `sla.view` |
| `GET` | `/api/v1/requisitions?...&sla_color=` | `requisition.view` + cálculo backend |
| `GET` | `/api/v1/requisitions/{id}/trace` | `requisition.history.view` |

El historial de evaluaciones sigue siendo append-only y cada evaluación registra color, etiqueta, base, horas, política, ámbito, disparador y actor.

## 6. Validación real

En el portal se cargaron tres requisiciones sintéticas:

| Folio | Estado administrativo | Semáforo | % surtido |
|---|---|---|---:|
| `REQ-LAG-2026-000003` | Autorizada parcial | En plazo | 0 % |
| `REQ-LAG-2026-000002` | Enviada | En plazo | 0 % |
| `REQ-LAG-2026-000001` | Autorizada parcial | En plazo | 0 % |

Totales: **3 verde, 0 amarillo, 0 rojo, 0 sin medición**. El filtro `sla_color=RED` devolvió HTTP 200 con cero filas. La respuesta incluyó los nuevos campos `equipment_id` y `requester_id`, necesarios para las columnas Equipo y Responsable.

Evidencia: `docs/evidencia/02_semaforo.png`.

## 7. Trazabilidad asociada

La vista `/trazabilidad/:requisitionId` muestra seis etapas:

1. Requisición
2. Autorización
3. Reserva
4. Entrega
5. Vale de almacén
6. Seguimiento SLA

Además lista autorizaciones, reservas, entregas, vales con enlaces PDF/Excel, eventos documentales y bitácora de auditoría. En la validación real se observaron 2 decisiones de autorización, 1 vale vinculado y eventos `VOUCHER_CREATE`, `VOUCHER_RENDERED`, `VOUCHER_REPRINTED` y `VOUCHER_SIGNATURES_RECORDED`.

Evidencia: `docs/evidencia/04_trazabilidad.png`.

## 8. Limitaciones

1. No hay notificaciones, recordatorios ni escalamiento automático.
2. No existe un job que evalúe periódicamente todas las requisiciones; el cálculo se hace al consultar.
3. No hay pantalla de configuración de políticas; los umbrales están sembrados y se cambian por servicio/migración autorizada.
4. El semáforo no bloquea la aprobación ni altera estados administrativos.
5. No usa calendario de días hábiles ni zona horaria `America/Mexico_City` para el cálculo de horas.
6. Las columnas Equipo y Responsable muestran `—` cuando la requisición no tiene esos campos capturados.
7. Sin conexión a CONTPAQi ni GMAO; sin puertos LAN; sin declaración de producción.
