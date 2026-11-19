# Evidencia de ejecución — Fase 3

**Fecha:** 2026-11-18
**Entorno:** Windows / PowerShell, PostgreSQL 17.12 real (`erp_minero_dev`, `erp_minero_test`), FastAPI + SQLAlchemy 2, React + Vite.
**Regla cumplida:** todos los comandos se ejecutaron localmente; no se hizo `git push`, despliegue ni conexión a sistemas externos.

---

## 1. Resumen de comandos y resultados reales

| Comando | Directorio | Salida | Código |
|---|---|---|---:|
| `pytest -q` | `backend` | `.......................................... [100%]` → 42 pruebas | 0 |
| `pytest -q tests/test_phase3_auth_rbac.py` | `backend` | `................ [100%]` → 16 pruebas nuevas | 0 |
| `ruff check .` | `backend` | `All checks passed!` | 0 |
| `mypy app` | `backend` | `Success: no issues found in 61 source files` | 0 |
| `python -m alembic current` | `backend` | `f3a9c1d7b2e4 (head)` | 0 |
| `npm.cmd run build` | `frontend` | `✓ 50 modules transformed`, `✓ built in 3.33s` | 0 |
| `npm.cmd run test -- --run` | `frontend` | `Test Files 2 passed (2)`, `Tests 7 passed (7)` | 0 |
| `git diff --check` | raíz | Sin errores; solo avisos `LF will be replaced by CRLF` propios de Windows | 0 |

El único aviso de Python es `StarletteDeprecationWarning` de `fastapi.testclient` por usar `httpx` con `TestClient`; no afecta a los resultados. En PowerShell se usa `npm.cmd` porque la política local bloquea `npm.ps1`.

## 2. Separación de pruebas nuevas y regresiones

Conteo real de `pytest -o addopts= --collect-only -q`:

| Archivo | Pruebas | Clasificación |
|---|---:|---|
| `tests/test_concurrency.py` | 1 | Regresión Fase 2 |
| `tests/test_inventory.py` | 6 | Regresión Fase 2 |
| `tests/test_postgres_phase2.py` | 8 | Regresión Fase 2 |
| `tests/test_purchases.py` | 5 | Regresión Fase 2 |
| `tests/test_requisitions.py` | 6 | Regresión Fase 2 |
| **Subtotal regresiones** | **26** | Todas conservadas y passing |
| `tests/test_phase3_auth_rbac.py` | 16 | **Nuevas Fase 3** |
| **Total** | **42** | `pytest -q` → 42 passed |

Frontend: `src/App.test.tsx` (4 pruebas) + `src/api/client.test.ts` (3 pruebas) = 7 pruebas.

## 3. Las 16 pruebas nuevas (PostgreSQL real)

Cada prueba usa la fixture `db`, que aplica migraciones, siembra datos sintéticos y revierte la transacción al terminar.

| # | Prueba | Comportamiento verificado | Resultado |
|---:|---|---|---|
| 1 | `test_login_valido_devuelve_sesion_y_cookies` | Login correcto; cookie `erp_session` con `HttpOnly` y `SameSite=lax`; CSRF en la respuesta; auditoría `LOGIN_SUCCESS` | PASSED |
| 2 | `test_contrasena_incorrecta_no_registra_secreto` | `401 Credenciales inválidas.`; `LoginAudit.reason=CREDENCIALES_INVALIDAS`; la contraseña fallida no aparece en la bitácora | PASSED |
| 3 | `test_usuario_inactivo_no_puede_entrar` | Cuenta `INACTIVE` → `401 La cuenta está inactiva.` y motivo `USUARIO_INACTIVO` | PASSED |
| 4 | `test_cambio_obligatorio_de_contrasena_inicial` | `demo.temporal` entra pero recibe `403` hasta cambiar la contraseña; tras el cambio opera normalmente | PASSED |
| 5 | `test_sesion_revocada_deja_de_ser_valida` | Revocar la sesión propia devuelve `204`; la petición siguiente con esa cookie da `401` | PASSED |
| 6 | `test_acceso_sin_sesion_es_rechazado` | `/auth/me`, `/catalogs` y `/audit` sin sesión → `401` | PASSED |
| 7 | `test_permisos_insuficientes_para_administrar` | Solicitante no puede crear usuarios: `403` y mensaje con `usuarios.administrar` | PASSED |
| 8 | `test_acceso_entre_departamentos_no_autorizados` | Requisición de `DEMO-OTRA`: detalle `403` y ausente en el listado del solicitante | PASSED |
| 9 | `test_usuario_con_varios_roles_acumula_permisos` | Asignar `AUDITOR` acumula `auditoria.consultar`; roles `{SOLICITANTE, AUDITOR}` | PASSED |
| 10 | `test_impide_autoautorizacion_de_requisicion` | El creador no puede autorizar su propia requisición: `403` con mensaje «propia requisición» | PASSED |
| 11 | `test_impide_escalada_de_privilegios` | Un solicitante no puede asignarse `ADMIN`: `403` y el rol no queda asignado | PASSED |
| 12 | `test_modificacion_de_roles_sin_autorizacion` | Sin `roles.asignar` no se puede quitar el rol `APROBADOR`: `403` | PASSED |
| 13 | `test_cambios_sensibles_quedan_en_auditoria` | Alta de usuario genera `USER_CREATED` con actor y entidad; un `UPDATE` sobre `aud.audit_log` falla por el trigger | PASSED |
| 14 | `test_restablecimiento_seguro_de_contrasena` | Contraseña temporal nueva; la antigua falla (`401`); la nueva obliga a cambiar; el temporal no aparece en la bitácora | PASSED |
| 15 | `test_proteccion_csrf_en_operaciones_con_cookies` | `POST /auth/logout` sin `X-CSRF-Token` → `403`; con token → `204` | PASSED |
| 16 | `test_no_acceso_a_registro_ajeno_por_identificador` | Acceso directo por UUID a otro departamento → `403 «No tiene acceso a registros de ese departamento.»` | PASSED |

## 4. Evidencia de base de datos

Salida real de `python -m alembic current`:

```text
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
f3a9c1d7b2e4 (head)
```

Conteo real de tablas base por esquema (`information_schema.tables` sobre `erp_minero_dev`):

```text
POR_ESQUEMA
seg 8
org 5
mdm 3
doc 4
req 2
wfl 3
inv 3
pur 4
mnt 1
cost 2
intg 3
aud 1
TOTAL 39
```

37 tablas provienen de la Fase 2; las 2 nuevas son `seg.user_session` y `seg.user_department`. No se recreó ni eliminó ninguna tabla.

## 5. Hallazgo detectado durante la verificación y corrección

Al ejecutar el archivo nuevo de forma aislada y después la suite completa, aparecieron 2 fallos en `tests/test_purchases.py`:

```text
FAILED tests/test_purchases.py::test_oc_por_faltantes_aprobacion_y_recepciones_parciales
FAILED tests/test_purchases.py::test_recepcion_duplicada_no_genera_nuevo_kardex
2 failed, 40 passed, 1 warning in 53.57s
```

Diagnóstico: las relaciones `PurchaseOrder.lines` y `Requisition.lines` no tenían `ORDER BY`, por lo que PostgreSQL devolvía las partidas en orden físico distinto entre la creación y las consultas posteriores. La recepción se aplicaba correctamente (stock y SQL directo confirmaban `received_qty=4`), pero la respuesta de la API lo mostraba en otra posición.

Corrección aplicada (sin migración, solo ORM):

```python
# app/modules/purchasing/models.py
lines: Mapped[list["PurchaseOrderLine"]] = relationship(
    back_populates="purchase_order", order_by="PurchaseOrderLine.line_no"
)

# app/modules/requisitions/models.py
lines: Mapped[list["RequisitionLine"]] = relationship(
    back_populates="requisition", order_by="RequisitionLine.line_no"
)
```

Verificación posterior: `pytest -q` → `.......................................... [100%]`, código 0; `ruff check .` y `mypy app` sin hallazgos. Este cambio se documenta también en `FASE3_RESULTADOS.md`.

## 6. Estado de Git y secretos

- Commit de recuperación: `c78b124 Agrega base PostgreSQL, migraciones y pruebas de la Fase 2`. **Sin push.**
- Los cambios de la Fase 3 están **sin commitear** en el directorio de trabajo.
- `.gitignore` excluye `.env` y `.env.*`, con excepción de `!.env.example`.
- `git diff --check` no reporta errores de whitespace; solo avisos de normalización LF→CRLF de Git en Windows.
- No se encontraron contraseñas, tokens ni cadenas de conexión con secretos en el diff; las contraseñas demo se leen de `DEMO_PASSWORD` y los hashes/jwt no se registran.

## 7. Alcance no cubierto

- No se ejecutaron circuitos transaccionales nuevos: las correcciones de idempotencia atómica, expiración de reservas y triple match de `docs/AUDITORIA_CODEX.md` siguen pendientes.
- No se contactó a CONTPAQi, Sierra Madre GMAO ni al servidor de la mina.
- No se hizo `git push`, tag ni despliegue.
