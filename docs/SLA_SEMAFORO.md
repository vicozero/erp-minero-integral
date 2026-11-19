# Semáforo SLA de requisiciones (Lote 2)

Fecha: 19/11/2026. Estado: **implementado y probado localmente**. El color es un indicador derivado calculado en el backend; **no sustituye al estado administrativo** de la requisición ni modifica inventario.

## 1. Política aprobada

El usuario aprobó los umbrales en horas de reloj transcurridas desde `submitted_at` (o `created_at` si aún no hay envío):

| Prioridad | Verde | Amarillo | Rojo |
|---|---:|---:|---|
| `LOW` | ≤ 72 h | ≤ 96 h | > 96 h |
| `NORMAL` | ≤ 48 h | ≤ 72 h | > 72 h |
| `HIGH` | ≤ 24 h | ≤ 48 h | > 48 h |
| `URGENT` | ≤ 8 h | ≤ 16 h | > 16 h |

Etiquetas mostradas: **En plazo** (`GREEN`), **En riesgo** (`YELLOW`), **Fuera de plazo** (`RED`) y **Sin medición** (`NONE`).

No se usan horas hábiles, calendario laboral ni pausas por fin de semana. Si se aprueba otra base de cálculo, debe crearse una nueva política con evidencia; no se reescriben evaluaciones antiguas.

## 2. Ámbito de las políticas

`req.sla_policy` permite combinar:

- prioridad (`LOW`, `NORMAL`, `HIGH`, `URGENT`);
- departamento (`ALL` o `department_id`);
- tipo de requisición (`ALL`, `STOCK`, `PURCHASE`, `SERVICE`).

La resolución elige la política activa **más específica**: primero departamento explícito sobre `ALL`, después tipo explícito sobre `ALL`. Los ámbitos posibles son `GLOBAL`, `DEPARTMENT`, `TYPE` y `DEPARTMENT+TYPE`. El `department_key` evita duplicados aunque PostgreSQL trate `NULL` como distinto en unicidades.

Las cuatro políticas `GLOBAL` se siembran de forma idempotente en la migración `d2e3f4a5b6c7` y en `app/db/seed.py`.

## 3. Cuándo no se mide

Devuelven `NONE` con `measured=false`:

- borradores (`DRAFT`);
- estados terminales `REJECTED`, `CANCELLED`, `CLOSED`;
- requisiciones sin política activa para su combinación.

En esos casos se devuelve un mensaje explicativo. El `status` administrativo se conserva sin cambios.

## 4. Emergencia

La emergencia está **desactivada por defecto** y solo puede aplicarse a `URGENT` mediante:

1. permiso `sla.policy.approve`;
2. motivo de al menos 8 caracteres;
3. registro de `emergency_approved_by` y `emergency_approved_at`;
4. auditoría (`SLA_EMERGENCY_APPROVE` / `SLA_EMERGENCY_DISABLE`) y evento de salida.

Plazos iniciales de emergencia: verde ≤ 4 h, amarillo ≤ 8 h. La restricción `ck_sla_policy_emergencia_aprobada` impide activarla aunque se escriba directamente en la base. Desactivar la emergencia limpia el aprobador y conserva el historial en bitácora.

## 5. Historial

`req.requisition_sla_event` es append-only. Cada fila guarda color, etiqueta, base temporal, horas transcurridas, política aplicada, ámbito, disparador, actor y contexto.

Disparadores implementados:

| Disparador | Momento |
|---|---|
| `ON_SUBMIT` | al enviar la requisición |
| `ON_DECIDE` | al aprobar o rechazar total o parcialmente |
| `ON_CANCEL` | al cancelar |
| `ON_CLOSE` | al cerrar por conciliación de partidas |
| `MANUAL` | evaluación explícita de requisiciones activas |

Cada evaluación emite además `REQUISITION_SLA_EVALUATED` al outbox en la misma transacción. No hay job automático: `POST /api/v1/sla/evaluate` permite generar instantáneas bajo demanda.

## 6. Permisos

| Permiso | Uso |
|---|---|
| `sla.view` | consultar políticas, requisiciones e historial |
| `sla.policy.configure` | crear/actualizar umbrales y evaluar manualmente |
| `sla.policy.approve` | activar o retirar emergencia |

`ADMIN` tiene los tres. `GERENCIA` cuenta con `sla.policy.approve`; los roles operativos y de lectura reciben `sla.view`. El alcance por departamento se aplica también a las consultas SLA: un usuario sin acceso a un departamento no puede ver su semáforo ni su historial.

## 7. API

| Método | Ruta | Permiso |
|---|---|---|
| `GET` | `/api/v1/sla/policies` | `sla.view` |
| `POST` | `/api/v1/sla/policies` | `sla.policy.configure` |
| `PATCH` | `/api/v1/sla/policies/{id}` | `sla.policy.configure` |
| `POST` | `/api/v1/sla/policies/{id}/emergency` | `sla.policy.approve` |
| `GET` | `/api/v1/sla/requisitions?sla_color=...` | `sla.view` |
| `GET` | `/api/v1/sla/requisitions/{id}` | `sla.view` |
| `GET` | `/api/v1/sla/requisitions/{id}/history` | `sla.view` |
| `POST` | `/api/v1/sla/evaluate?department_id=...` | `sla.policy.configure` |

Además, `GET /api/v1/requisitions?sla_color=RED` filtra usando el color ya calculado por `SlaService` dentro de `RequisitionOut.sla`. La respuesta de historial incluye `label` para que la interfaz no traduzca ni recalcule el color.

Ejemplo de indicador devuelto en una requisición:

```json
{
  "color": "YELLOW",
  "label": "En riesgo",
  "measured": true,
  "administrative_status": "SUBMITTED",
  "elapsed_hours": "30.00",
  "policy_scope": "GLOBAL",
  "emergency_active": false
}
```

## 8. Frontend

La pantalla `Requisiciones` muestra:

- una columna **Semáforo** con etiqueta textual y color, separada de la columna **Estado**;
- un filtro **Semáforo SLA** que envía `sla_color` al backend;
- un botón **Historial SLA** con instantáneas, disparador, ámbito, horas y actor.

El navegador solo representa el `color` y el `label` recibidos; no calcula plazos ni decide colores. El título accesible del chip recuerda que el indicador no sustituye al estado administrativo.

## 9. Migración y trazabilidad

- Migración aditiva `d2e3f4a5b6c7`, dependiente de `c1d2e3f4a5b6`; crea dos tablas en `req` y siembra cuatro políticas. `downgrade()` falla deliberadamente.
- Auditoría: `SLA_POLICY_CREATE`, `SLA_POLICY_UPDATE`, `SLA_EMERGENCY_APPROVE`, `SLA_EMERGENCY_DISABLE`.
- Eventos: `SLA_POLICY_CREATED`, `SLA_POLICY_UPDATED`, `SLA_EMERGENCY_ENABLED`, `SLA_EMERGENCY_DISABLED`, `REQUISITION_SLA_EVALUATED`.

## 10. Limitaciones

1. No hay notificaciones ni escalamiento automático; solo evaluación manual y consulta.
2. El color no detiene ni acelera flujos de aprobación.
3. No se modificó CONTPAQi ni GMAO; no se usaron datos reales.
4. No se expuso la API fuera de `127.0.0.1` y no se hizo `push`.
5. Esta entrega no declara el sistema apto para producción.
