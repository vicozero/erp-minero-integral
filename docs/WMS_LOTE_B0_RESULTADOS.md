# WMS Lote B.0 — Resultados

> Fecha: 2026-11-19  
> Alcance: **únicamente Lote B.0** (contratos, permisos y bandera).  
> Estado: B.0 completado y verificado localmente. **El Lote B NO se declara completo.**  
> Base de pruebas: PostgreSQL real `erp_minero_test`, migraciones Alembic `head`. No se usó SQLite.

---

## 1. Commit de documentación

| Concepto | Valor |
|---|---|
| Commit | `b100013` |
| Mensaje | `Documenta arquitectura transaccional del Lote B WMS` |
| Archivos | `docs/WMS_LOTE_B_DISENO.md`, `docs/WMS_LOTE_B_PLAN.md`, `docs/WMS_LOTE_B_RIESGOS.md` |
| Push | **No realizado** |

Se verificó previamente que solo esos tres archivos estaban pendientes, con UTF-8 válido, sin BOM y sin patrones de credenciales.

---

## 2. Actividades B.0 ejecutadas

| Actividad | Resultado |
|---|---|
| Mostrar archivos previstos antes de editar | Ejecutado. Alcance: `constants.py`, `config.py`, `wms_movement_schemas.py` (nuevo) y `test_lote_b_contracts.py` (nuevo). |
| Identificar migraciones | `(ninguna)`. |
| Revisar compatibilidad | Requisiciones, reservas y compras intactos; servicios y modelos heredados sin cambios. |
| Confirmar comportamiento heredado | `almacenes.kardex -> inventory.kardex.view` conservado; claves de idempotencia y endpoints actuales sin cambios. |
| Permisos canónicos | Agregados `wms.receipt.create/approve`, `wms.issue.create/approve`, `wms.return.create/approve`, `wms.reversal.create/approve`, `wms.kardex.view`, `warehouse.stock.view`. |
| Aliases en español | `almacenes.entradas/salidas/devoluciones/reversos` y `entradas.crear`, `salidas.crear`, `devoluciones.crear`, `reversos.crear`, todos resueltos a los permisos canónicos de creación. |
| Roles | `ALMACENISTA`/`ALMACEN`: creación + consulta. `APROBADOR`: aprobación + consulta. `GERENCIA`/`AUDITOR`: solo consulta. `ADMIN`: todos. |
| Feature flag | `WMS_LOTE_B_ENABLED: bool = False` en `app/core/config.py`. |
| Esquemas Pydantic v2 | `ReceiptIn`, `IssueInWms`, `ReturnIn`, `ReversalIn`, `MovementOrderOut` (+ `MovementOrderLineOut`) y `KardexEntryOut`, con `Decimal`/`UUID`, sin `float`. |
| Registro de routers | **Ninguno.** No se creó `wms_movements.py` ni se tocó `app/main.py`. |
| Operaciones dependientes de decisiones pendientes | **Detenidas por diseño.** B.0 solo declara formas de datos; no ejecuta devoluciones, cuarentena, vencimientos ni selección FEFO/FIFO. |

### Archivos modificados o creados

```text
M backend/app/core/config.py
M backend/app/shared/constants.py
A backend/app/modules/inventory/wms_movement_schemas.py
A backend/tests/unit/test_lote_b_contracts.py
A docs/WMS_LOTE_B0_RESULTADOS.md
```

---

## 3. Migraciones nuevas

**Ninguna.** No se crearon ni modificaron archivos en `backend/migrations/versions/`. La migración `b7c8d9e0f1a2_lote_b_movimientos_wms.py` corresponde al Lote B.1 y **no** se aplicó.

## 4. Tablas modificadas

**Ninguna.** No se ejecutaron `CREATE`, `ALTER`, `DROP`, `TRUNCATE` ni `DELETE` sobre tablas de negocio. El único acceso a base de datos fue el arnés existente de `pytest`, que aplica Alembic `head` y re-siembra datos **sintéticos** en `erp_minero_test`.

---

## 5. Pruebas ejecutadas

| Verificación | Comando | Resultado |
|---|---|---|
| Pruebas B.0 | `python -m pytest tests/unit/test_lote_b_contracts.py -q` | **9 pasadas** |
| Suite backend completa | `python -m pytest -q --tb=short` | **77 pasadas** (68 base + 9 nuevas) |
| Lint | `python -m ruff check app tests` | `All checks passed!` |
| Tipado | `python -m mypy app` | `Success: no issues found in 66 source files` |
| Diferencias | `git diff --check` | Sin errores |
| Frontend / build React / portal | No ejecutados | Sin cambios frontend en B.0; no correspondía según el plan. |

Nota de infraestructura: el primer intento de prueba falló porque el servicio PostgreSQL local se terminó de forma anómala (`0xC0000409` en `postgres.exe`, `PANIC: no se pudo abrir global/pg_control`). Se reinició el servicio local, enlazado a `127.0.0.1`, y las ejecuciones mostradas arriba terminaron correctamente. No se modificó configuración de red ni de base de datos.

---

## 6. Riesgos abiertos

| Riesgo | Control en B.0 | Seguridad posterior |
|---|---|---|
| Activación accidental de endpoints nuevos | `WMS_LOTE_B_ENABLED=False` y cero routers registrados | B.3 en adelante: registro condicional |
| Permisos huérfanos o aliases ambiguos | Pruebas de registro, resolución y asignación por rol | B.8: cableado RBAC y alcance |
| Contratos con `float` o precisión incorrecta | `Decimal` con `NUMERIC(18,6)` / importes `(18,4)` en esquemas | B.1/B.3: constraints y servicio |
| Doble salida, reversos duplicados, divergencia agregado/detalle | No aplica: B.0 no ejecuta movimientos | B.1/B.2/B.4/B.6: triggers, índices parciales, bloqueos |
| Caída del PostgreSQL local | Reinicio del servicio; sin cambios de esquema | Verificar estabilidad antes de B.1 |

---

## 7. Decisiones pendientes (sin aprobación)

1. Confirmar si las devoluciones deben descontar `line_delivered_qty` (en el diseño no: solo los reversos lo hacen).
2. Definir autorizador formal para liberación de cuarentena.
3. Definir si `expiry_date` vencida bloquea o solo advierte.
4. Decidir cuándo ejecutar `inv.backfill_lote_b_detail()` en el piloto.
5. Confirmar política FEFO vs FIFO por familia de artículo.

Ninguna de las decisiones bloqueó B.0. Las operaciones que dependen de ellas quedan **sin implementar**.

---

## 8. Estado del repositorio

- Commit de documentación `b100013` ya creado; **sin push**.
- Cambios B.0 en el árbol de trabajo, listos para commit local del lote.
- Sin secretos, datos reales, `0.0.0.0`, comandos destructivos ni conexiones a CONTPAQi/GMAO en el diff.
- Inventario heredado, compras y requisiciones sin modificaciones.

---

## 9. Próximo lote recomendado

**Lote B.1 — Migración aditiva.** Crear `b7c8d9e0f1a2_lote_b_movimientos_wms.py` con `down_revision = a1b2c3d4e5f6`, verificar `empty -> head` solo en base sintética y mantener `downgrade()` con `RuntimeError`. No ejecutar backfill automático.

---

## 10. Limitaciones

- B.0 no habilita funcionalidad operativa: la bandera está apagada y no existen endpoints WMS de movimientos.
- No se ejecutaron pruebas de concurrencia ni de integridad transaccional: pertenecen a B.1/B.2 en adelante.
- Las cinco decisiones empresariales siguen requiriendo aprobación explícita antes de implementar sus operaciones dependientes.
