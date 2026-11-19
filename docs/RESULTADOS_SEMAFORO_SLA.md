# Resultados — Semáforo SLA (Lote 2)

Fecha: 19/11/2026. Estado: **backend y frontend implementados y probados localmente**. Contrato detallado en `docs/SLA_SEMAFORO.md`.

> **Actualización Lote 5:** el tablero operativo con filtros, columnas de equipo/responsable y trazabilidad asociada está documentado en `docs/SEMAFORO_REQUISICIONES.md`.

## Decisiones aprobadas

| Tema | Decisión |
|---|---|
| Base temporal | `submitted_at`, con respaldo `created_at` |
| `LOW` | verde ≤ 72 h, amarillo ≤ 96 h, rojo > 96 h |
| `NORMAL` | verde ≤ 48 h, amarillo ≤ 72 h, rojo > 72 h |
| `HIGH` | verde ≤ 24 h, amarillo ≤ 48 h, rojo > 48 h |
| `URGENT` | verde ≤ 8 h, amarillo ≤ 16 h, rojo > 16 h |
| Emergencia | desactivada; 4/8 h solo con aprobación `sla.policy.approve` |
| Exposición visual | chip separado del estado, filtro e historial en `Requisiciones` |

## Cambios entregados

### Backend

- Permisos `sla.view`, `sla.policy.configure`, `sla.policy.approve` y constantes de colores/ámbitos.
- Modelos `req.sla_policy` y `req.requisition_sla_event`, con historial append-only y restricción de emergencia aprobada.
- Migración aditiva `d2e3f4a5b6c7` y siembra idempotente de cuatro políticas `GLOBAL`.
- Servicio de resolución por ámbito, cálculo, instantáneas, consultas y aprobación de emergencia.
- Router `/api/v1/sla/...` registrado en `app.main`.
- `RequisitionOut.sla` con el indicador derivado; instantáneas en `ON_SUBMIT`, `ON_DECIDE`, `ON_CANCEL`, `ON_CLOSE` y `MANUAL`.
- Filtro `sla_color` en `GET /api/v1/requisitions` usando el color calculado por el backend.
- Pruebas en `tests/test_sla.py` y ajustes en pruebas de esquema/migración.

### Frontend

- Tipos `SlaResult`, `SlaEvaluation`, `SlaColor` y `RequisitionFilters.sla_color`.
- Cliente API con `slaHistory`.
- Componente `SlaBadge` con etiqueta textual, color y aviso accesible de que no sustituye al estado.
- Filtro de semáforo, columna separada del estado y panel `Historial SLA`.
- Estilos diferenciados de los badges administrativos.

## Verificación ejecutada

```powershell
cd E:\ERP_MINERO\backend
python -m ruff check app
python -m mypy app/modules/sla app/api/v1/routers/sla.py tests/test_sla.py --follow-imports=silent
python -m pytest -q

cd E:\ERP_MINERO\frontend
npm.cmd run test -- --run
npm.cmd run build
```

Resultados:

- `ruff check app`: sin errores.
- `mypy`: sin errores en los seis archivos SLA revisados.
- Backend: **109 pruebas aprobadas** sobre PostgreSQL `erp_minero_test`; sin SQLite.
- Alembic: `d2e3f4a5b6c7 (head)` verificado en `erp_minero_test` tras la migración.
- Frontend: **27 pruebas aprobadas** en 8 archivos y compilación de producción correcta.
- Las pruebas cubren umbrales, específicidad de políticas, historial inmutable, alcance por departamento, emergencia auditada con restricción en base, filtro por color y ausencia de movimientos de kardex al evaluar.

## Cadena de custodia

- Toda evaluación persistente registra color, etiqueta, base, horas, política, ámbito, disparador y actor.
- Cambios de política y emergencia quedan en bitácora con `before`/`after` y motivo.
- Cada evaluación emite `REQUISITION_SLA_EVALUATED` al outbox en la misma transacción.
- El frontend no calcula plazos: solo presenta los valores devueltos por el backend.

## Limitaciones conocidas

1. No hay notificaciones, recordatorios ni escalamiento automático.
2. El semáforo no bloquea aprobaciones ni altera estados administrativos.
3. El cálculo usa horas de reloj, no horas hábiles de `America/Mexico_City`.
4. No se conectó a CONTPAQi ni GMAO y no se usaron datos reales.
5. No se publicaron puertos, no hubo `push` y no se declara apto para producción.

## Siguiente paso

Implementar el **almacén virtual** con jerarquía unidad → almacén → zona → pasillo → rack → nivel → posición, plano 2D sobre fondo autorizado, panel lateral, permisos, QR y coordenadas editables. Después, ejecutar la regresión integral backend/frontend.
