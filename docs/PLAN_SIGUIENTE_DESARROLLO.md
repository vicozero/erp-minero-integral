# Plan siguiente de desarrollo

## 1. Principio rector

No ampliar funcionalidad transaccional hasta cerrar las decisiones de negocio que afectan inventario oficial, valuación y aprobaciones. Toda entrega debe incluir migración aditiva, pruebas, bitácora y verificación local; nunca se declarará apta para producción sin piloto y revisión formal.

## 2. Prioridad 0 · Decisiones de negocio (bloqueantes)

| Decisión | Por qué bloquea | Resultado esperado |
| --- | --- | --- |
| Política de valuación (FIFO, promedio o estándar) | Define capas y asientos de `costing` | Documento aprobado con ejemplo numérico |
| Lotes y series obligatorios por familia | Define validaciones de recepción y surtido | Matriz familia → control obligatorio |
| Jerarquía de ubicación y reglas de mezcla | Define restricciones y transferencias | Esquema `almacén > zona > pasillo > estante > nivel > posición` aprobado |
| Modelo de herramientas | Define si son activos, consumibles o retornables | Altas, control de series y baja |
| Esquema físico `wms` frente a esquemas actuales | Define estabilidad de migraciones | Decisión formal; mientras tanto se conserva `mdm`/`inv` |
| Aprobadores de diferencias y reversiones | Define workflow y bitácora | Matriz de roles y límites |

## 3. Prioridad 1 · Fase 3: Requisiciones y autorizaciones visuales

**Alcance**

- Refinar tablas, filtros y estados de `Requisitions`, `Approvals` e `History` con el sistema visual ya aplicado al Dashboard y WMS.
- Mostrar partidas con cantidades solicitada, autorizada, reservada, comprada, recibida y entregada, derivadas de tablas de detalle.
- Mensajes de error accionables y explicación visible de por qué una partida no puede autorizarse.
- Sin cambios en reglas de workflow ni en transacciones de stock.

**Criterios de aceptación**

- Pruebas frontend nuevas para estados parciales y rechazo con motivo.
- `npm run build` y `vitest` en verde.
- Verificador de portal ampliado con al menos una comprobación de la vista de autorizaciones.
- Captura o texto real del DOM guardado en `docs/evidencias_demo/`.

## 4. Prioridad 2 · Lote B de WMS: movimientos y etiquetas

**Alcance**

- Transferencias entre ubicaciones con orden determinístico de bloqueo.
- Recepción y surtido asistidos por token de etiqueta.
- Generación y lectura de QR gráfico; el token legible actual es solo la base.
- Reservas y entregas desde la ficha de material, siempre vía `InventoryService`.

**Criterios de aceptación**

- Idempotencia y transacción única para cada movimiento.
- Auditoría y outbox en la misma transacción.
- Pruebas de concurrencia ligera y de reversión por contrapartida, nunca borrado.
- Sin escritura directa a tablas de otro módulo.

## 5. Prioridad 3 · Triple match y compras

- Emparejar OC, recepción y factura con tolerancias aprobadas.
- Diferencias visibles con estado y aprobador, sin publicar asientos a CONTPAQi.
- Reporte de compromisos y recibido pendiente de facturar.

## 6. Prioridad 4 · Integraciones controladas

- CONTPAQi: solo importación de archivos controlados vía `integration_batch` → `integration_staging` → validación → destino, previa autorización.
- GMAO: solo `external_gmao_id`, estado de sincronización y eventos en `intg.gmao_sync_event`; sin escritura en Sierra Madre.
- Hash, tamaño, usuario y resultado de cada archivo registrados.

## 7. Prioridad 5 · Endurecimiento y piloto

1. Crear `erp_minero_pilot` solo con autorización expresa y ejecutar Alembic `empty -> head`.
2. Normalizar el CHECK con doble prefijo mediante migración revisada y aprobada; no ejecutar sobre datos reales sin ticket.
3. Revisar cabeceras de seguridad y CSRF bajo el FQDN autorizado.
4. Activar LAN/TLS/DNS/firewall/certificado únicamente con autorización formal.
5. Definir respaldo, restauración y prueba de recuperación.

## 8. Backlog técnico menor

- Sustituir los códigos HTTP de deprecación `HTTP_422_UNPROCESSABLE_ENTITY` por `HTTP_422_UNPROCESSABLE_CONTENT`.
- Revisar advertencias de React Router v7 en las pruebas.
- Añadir auditoría de accesibilidad con Lighthouse a las rutas WMS.
- Limpiar artefactos generados por build antes de cada checkpoint.

## 9. Fuera de alcance por decisión actual

- No modificar CONTPAQi ni GMAO.
- No usar datos reales de producción.
- No crear un segundo inventario oficial.
- No publicar puertos, abrir firewall ni exponer el servicio.
- No ejecutar `downgrade`, `DROP`, `TRUNCATE` ni borrados masivos.
- No hacer `git push` sin instrucción explícita.

## 10. Definición de terminado para el siguiente lote

- Código con tipos y lint limpios.
- Pruebas nuevas y existentes en verde.
- Migración aditiva probada de `empty` a `head`.
- Sin secretos ni datos reales en el diff.
- Bitácora y eventos cubriendo acciones sensibles.
- Documentación actualizada y evidencia real guardada.
- Limitaciones y siguiente paso indicados explícitamente.
