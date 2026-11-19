# Evidencia de la mejora de Requisiciones y Autorizaciones

**Fecha:** 19/11/2026  
**Entorno:** PostgreSQL local activo (`postgresql-x64-17`), API `127.0.0.1:8000`, portal `127.0.0.1:8080`.  
**Datos:** exclusivamente sintéticos, creados por los scripts de verificación. No se usaron datos de CONTPAQi, GMAO ni producción. No se imprimió ninguna credencial.

## 1. Índice de archivos

| Archivo | Contenido |
| --- | --- |
| `01_catalogo_ficha_material.txt` | Evidencia previa del catálogo WMS. |
| `02_ubicaciones_ficha.txt` | Evidencia previa de ubicaciones WMS. |
| `03_verificacion_portal.txt` | Verificación base del portal. |
| `04_backend_pytest.txt` | Línea base backend anterior. |
| `05_frontend_vitest.txt` | Línea base frontend anterior (14 pruebas). |
| `06_verificar_portal_requisiciones.txt` | Verificación ampliada del portal: 30/30. |
| `07_flujo_demo_requisiciones.txt` | Circuito real de requisición y autorización parcial: 11/11. |
| `08_backend_pytest_final.txt` | Resultado final de pytest backend. |
| `09_frontend_vitest_final.txt` | Resultado final de Vitest: 25/25. |
| `10_build_frontend.txt` | Salida real de `npm run build`. |
| `11_dom_dashboard.txt` | Texto real del DOM del Dashboard. |
| `12_dom_requisiciones.txt` | Texto real del DOM del listado de requisiciones. |
| `13_dom_autorizaciones_pendiente.txt` | Texto real del DOM de la bandeja con un documento `SUBMITTED`. |
| `14_dom_historial.txt` | Texto real del DOM de eventos y bitácora. |

## 2. Línea base

Antes de tocar código, PostgreSQL estaba detenido y Alembic agotó el timeout en `tests/conftest.py` (68 errores). Se inició el servicio local sin cambiar configuración ni exponer red:

```text
postgresql-x64-17 — Running
```

Línea base posterior:

```text
backend:  68 passed, 5 warnings in 121.36s
frontend: 14 passed (5 archivos)
```

## 3. Verificación del portal en vivo

`python scripts/verificar_portal.py` comprobó:

- health del backend y health/db detrás del proxy;
- rutas SPA `/`, `/login`, `/requisiciones`, `/autorizaciones`, `/historial`, `/catalogo`, `/ubicaciones` y `/almacen`;
- bundle React, API relativa sin origen hard-codeado y `Content-Type` correcto;
- login, cookies `HttpOnly`, CSRF disponible, `SameSite` y ausencia de `Secure` en HTTP local;
- listado de requisiciones, bitácora e historial;
- WMS: familias, búsqueda avanzada con existencia, ubicaciones con ocupación y ficha de material;
- CSRF exigido en escrituras (403) y logout con CSRF válido (204).

Resultado: **30/30**.

## 4. Circuito demo real

`python scripts/verificar_flujo_demo.py` usó las cuentas sintéticas `demo.solicitante`, `demo.aprobador` y `demo.admin` con la contraseña ficticia de `.env`, leída en memoria y nunca impresa.

```text
Documento sintético verificado: REQ-LAG-2026-000003
[OK] Login solicitante demo
[OK] Login aprobador demo
[OK] Login administrador demo
[OK] Catálogos para la captura — 3 artículos disponibles
[OK] Creación de requisición de prueba — HTTP 201
[OK] Envío a autorización — HTTP 200
[OK] Dos partidas disponibles para decisión — 2 partida(s)
[OK] Autorización parcial por partida — HTTP 200 · PARTIALLY_APPROVED
[OK] Estados de partida derivados — PARTIAL, AUTHORISED
[OK] Seguimiento por partida — 2 partida(s) pendiente(s)
[OK] Historial del documento — DOCUMENT_NUMBER_ISSUED, REQUISITION_CREATED,
     REQUISITION_SUBMITTED, REQUISITION_DECIDED

Resultado: 11/11 verificaciones del circuito correctas.
```

Las capturas de DOM se tomaron sobre `REQ-LAG-2026-000001` (autorizado parcialmente) y `REQ-LAG-2026-000002` (creado con el mismo patrón y dejado en `SUBMITTED` únicamente para evidenciar la bandeja de autorizaciones en la UI). No se registró ninguna decisión sobre `000002` durante la captura. La ejecución final del verificador generó `REQ-LAG-2026-000003`, cuyo resultado es el que aparece en `07_flujo_demo_requisiciones.txt`.

## 5. Evidencia visual en navegador

Se inició sesión real en el navegador con `demo.admin`. La contraseña se copió al portapapeles desde `.env` sin mostrarla y se sobrescribió al terminar. Se recorrieron las rutas del menú y se capturó el texto real del DOM.

Hechos comprobados en pantalla:

- Dashboard: KPIs reales y bloque «Indicadores no disponibles con la API actual».
- Requisiciones: `REQ-LAG-2026-000001` con partidas `10/4/0/4` y `6/6/0/6` (solicitada/autorizada/entregada/pendiente).
- Autorizaciones: bandeja con `REQ-LAG-2026-000002`, prioridad `HIGH`, 2 partidas y botones de decisión.
- Historial: eventos del documento con actor y transición de estado; bitácora con actor, acción y `request_id`.
- Almacén: pantalla operativa sin movimientos registrados para el alcance del usuario.

No se pudieron generar imágenes: la herramienta de navegador informó `UnknownVizError` al hacer clic y, al intentar capturar, indicó que la pestaña no estaba visible. Por ello la evidencia visual se conserva como texto del DOM, no como captura PNG.

## 6. Pruebas automatizadas nuevas

- `Requisitions.test.tsx`: 5 pruebas (búsqueda por número de parte, validación de cantidad, edición con PATCH, confirmación de cancelación, actor en historial).
- `Approvals.test.tsx`: 4 pruebas (cantidad editada, rechazo parcial sin cancelar otras líneas, guard de doble envío, mensaje accionable en 403).
- `Dashboard.test.tsx`: 2 pruebas (KPIs y degradación parcial).
- `History.test.tsx`: 2 pruebas (sin permiso de auditoría y con bitácora disponible).

Resultado final: **25/25 pruebas frontend** en 8 archivos. Backend: **68/68**.

## 7. Declaración

No se guardaron secretos en los archivos de evidencia. Los UUID de actores y solicitudes aparecen truncados en las capturas de DOM porque así los muestra la interfaz; la base de datos conserva los valores completos. La evidencia corresponde a un entorno local de demostración y no demuestra aptitud para producción.
