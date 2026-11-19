# Avance visual y de presentación — Requisiciones

**Fecha:** 19/11/2026  
**Portal:** `http://127.0.0.1:8080` · API detrás del proxy en `http://127.0.0.1:8000`.  
**Público objetivo:** demostración local al cliente de la unidad minera La Guitarra.

## 1. Qué puede verse hoy

La experiencia completa de captura → envío → autorización → seguimiento está recorrible desde el menú lateral, con los mismos permisos que ya existían en el backend.

1. **Dashboard**: resume el estado real del documento demo, muestra el surtido por unidad y marca como no disponibles los indicadores que la API no puede sustentar.
2. **Requisiciones**: formulario guiado, buscador WMS por número de parte, resumen por UOM, borradores editables, adjuntos e historial por documento.
3. **Autorizaciones**: bandeja con metadatos, decisión por partida y confirmaciones antes de escribir.
4. **Historial**: línea de tiempo con actor y bitácora de auditoría sujeta a permisos.
5. **Almacén / Catálogo / Ubicaciones / Compras**: pantallas existentes siguen operativas; el rediseño no las rompió.

## 2. Criterios visuales aplicados

- **Jerarquía clara:** encabezado con subtitle accionable, paneles por bloque de trabajo y botones primarios/secundarios/peligrosos diferenciados.
- **Terminología minera en español:** folio, partida, almacén, centro de costo, equipo, surtido, autorizar, rechazar.
- **Unidades separadas:** ningún KPI suma kilogramos con piezas; cada UOM conserva su propia fila.
- **Estados legibles:** `StatusBadge` y `PriorityBadge` con colores distintos para borrador, enviado, parcial, autorizado, rechazado y cancelado.
- **Errores accionables:** 401, 403, 409 y 422 se traducen a mensajes que indican la causa probable sin exponer detalles técnicos ni secretos.
- **Accesibilidad básica:** diálogos con `role="dialog"`, `aria-modal`, etiquetas en campos y `aria-label` en controles de partidas; estilos para movimiento reducido.
- **Tema claro/oscuro y responsive:** el navegador respeta la preferencia del sistema y los paneles se reacomodan en pantallas estrechas.

## 3. Guion de demostración sugerido (5 minutos)

1. Abrir `http://127.0.0.1:8080` e iniciar sesión con una cuenta ficticia definida en `.env`.
2. En **Dashboard**, señalar los KPIs y el bloque de indicadores no disponibles; explicar que no se inventan montos ni SLA.
3. En **Requisiciones**, abrir `REQ-LAG-2026-000001` y revisar las partidas `10/4/0/4` y `6/6/0/6`; recalcar que autorizado y entregado vienen del servidor.
4. Crear una requisición nueva: seleccionar artículo por número de parte, agregar dos partidas con distinta UOM, guardar borrador y enviar. Mostrar el diálogo de confirmación.
5. En **Autorizaciones**, abrir `REQ-LAG-2026-000002`, editar una cantidad, marcar una partida como no incluida y observar el diálogo antes de `POST /decide`. No es necesario ejecutar la decisión en la demo.
6. En **Historial**, mostrar `REQUISITION_DECIDED` con actor y el evento de bitácora correspondiente con `request_id`.
7. Cerrar sesión. No publicar el portal ni compartir credenciales.

## 4. Evidencias disponibles

- Texto real del DOM: `docs/evidencias_demo/11_dom_dashboard.txt` a `14_dom_historial.txt`.
- Salidas de verificación: `06_verificar_portal_requisiciones.txt`, `07_flujo_demo_requisiciones.txt`, `08_backend_pytest_final.txt`, `09_frontend_vitest_final.txt` y `10_build_frontend.txt`.
- Detalle técnico: `docs/MEJORA_REQUISICIONES_RESULTADOS.md`.
- Trazabilidad de la evidencia: `docs/EVIDENCIA_REQUISICIONES.md`.

No hay capturas PNG: la herramienta de navegador no pudo hacerlas visibles en esta sesión. La evidencia textual proviene del DOM real del portal autenticado.

## 5. Pendiente para la siguiente presentación

- Generar capturas reales desde un navegador con visibilidad de pantalla y adjuntarlas a `docs/evidencias_demo/`.
- Repetir la narrativa con un aprobador dedicado (`demo.aprobador`) para mostrar el cambio de permisos entre roles.
- Formalizar las decisiones de negocio que hoy se muestran como no disponibles: solicitante por documento, valuación, SLA y jerarquía de ubicaciones.
- Ejecutar la prueba Alembic `empty -> head` en una base piloto autorizada antes de cualquier instalación fuera de local.

**Estado:** demostrable en local con datos sintéticos. No se afirma aptitud para producción, intranet ni exposición de red.
