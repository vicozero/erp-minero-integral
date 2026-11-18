# AGENTS.md — ERP MINERO INTEGRAL

## 1. Propósito

Este archivo define las reglas de trabajo para agentes, desarrolladores y automatizaciones (incluido OpenCode) en este repositorio.

**Ubicación física detectada:** `E:\ERP_MINERO`  
**Ubicación lógica referida por el usuario:** `C:\ERP_MINERO`  
**Estado:** `C:\ERP_MINERO` no existe en este entorno; no se crearon enlaces ni se modificó infraestructura. Toda documentación se creó en `E:\ERP_MINERO`. Si se decide migrar el proyecto, confirmar antes de copiar o mover archivos.

## 2. Contexto del negocio

La unidad minera **La Guitarra** usa actualmente **CONTPAQi Comercial Premium 11.5.1** por Escritorio Remoto. El nuevo ERP será web, inicialmente local y preparado para intranet, múltiples usuarios, departamentos, almacenes y unidades mineras.

Sierra Madre GMAO y CONTPAQi son sistemas externos. Este proyecto **no los modifica**.

## 3. Principios rectores

1. **Modularidad antes que microservicios.** Iniciar como un monolito modular FastAPI con límites de dominio explícitos.
2. **El inventario operativo no es el inventario oficial.** CONTPAQi permanece como sistema oficial de inventario/contabilidad hasta que exista una decisión formal de migración.
3. **Trazabilidad por documento.** Todo movimiento relevante nace de un documento con número único, tipo, serie, usuario, timestamp y evento de auditoría.
4. **Transaccionalidad del stock.** Toda operación que afecte existencias, reservas o costos se ejecuta en una única transacción con bloqueos y clave de idempotencia.
5. **Append-only para hechos contables y de inventario.** No se eliminan ni se sobrescriben movimientos; las correcciones son contrapartidas o reversiones.
6. **Migraciones aditivas.** Alembic nunca debe eliminar datos en migraciones automáticas. Las operaciones destructivas requieren aprobación explícita y ticket.
7. **Sin datos reales sin autorización.** Semillas, pruebas y demostraciones usan datos sintéticos.
8. **Sin exposición de red.** Durante desarrollo el servidor escucha solo en `127.0.0.1`. No publicar puertos, no abrir firewall, no usar `0.0.0.0`.
9. **Sin credenciales en el repositorio.** Configuración por variables de entorno o gestor de secretos. Los ejemplos no contienen valores reales.
10. **No afirmar finalización sin pruebas.** Todo cambio debe incluir pruebas automatizadas y pasarlas localmente.

## 4. Prohibiciones explícitas

- No modificar Sierra Madre GMAO, CONTPAQi ni otros sistemas.
- No conectarse a bases de datos de CONTPAQi.
- No extraer información real de producción sin autorización por escrito.
- No crear un segundo inventario oficial.
- No eliminar, truncar, sobrescribir ni renombrar archivos o datos preexistentes.
- No ejecutar `DROP`, `TRUNCATE`, `DELETE` masivo ni `alembic downgrade` sobre datos reales.
- No exponer servicios a la red local o pública sin autorización.
- No guardar contraseñas, tokens, cadenas de conexión con secretos, llaves ni certificados en Git.
- No usar `float` para cantidades o dinero; usar `NUMERIC`.
- No inventar estados de aprobación ni saltarse reglas de workflow.

## 5. Estructura y límites de dominio

```text
backend/app/modules/
  identity/        Usuarios, roles, permisos, RBAC con alcance
  organization/    Empresa, unidad minera, departamento, almacén, empleado
  master_data/     Artículos, UOM, proveedores, ubicaciones mineras, lotes, series
  requisitions/    Requisiciones y líneas
  workflow/        Políticas, pasos, decisiones y eventos de aprobación
  inventory/       Saldos, movimientos, reservas, ajustes, conciliaciones
  purchasing/      Órdenes de compra, recepciones, facturas, triple match
  maintenance/     Equipos, medidores, órdenes de trabajo, consumo de materiales
  costing/         Centros de costo, objetos de costo, asientos y capas de valuación
  integrations/    Adaptadores de CONTPAQi y GMAO; staging, outbox, inbox
  audit/           Bitácora inmutable y auditoría de acceso
  shared/          Numeración, idempotencia, eventos, errores, paginación
```

Regla de dependencia: los routers llaman a servicios; los servicios a repositorios; los repositorios a SQLAlchemy. Los modelos de dominio no importan FastAPI. Los módulos se comunican mediante interfaces de servicio o eventos, nunca accediendo directamente a tablas de otro módulo.

## 6. Convenciones de código

### Backend

- Python 3.12+, type hints obligatorios en firmas públicas.
- FastAPI con routers versionados bajo `/api/v1`.
- Pydantic v2 para esquemas de entrada/salida.
- SQLAlchemy 2 estilo declarativo, `Mapped[...]` y `mapped_column`.
- Alembic para todo cambio de esquema.
- Nombres de tablas en `snake_case`, agrupados en esquemas PostgreSQL: `seg`, `org`, `mdm`, `doc`, `req`, `wfl`, `inv`, `pur`, `mnt`, `cost`, `intg`, `aud`.
- Claves primarias `UUID`.
- Cantidades `NUMERIC(18,6)`; importes `NUMERIC(18,2)` o `NUMERIC(18,4)` cuando se requiera precisión fiscal.
- Timestamps `TIMESTAMPTZ`; zona de referencia `America/Mexico_City`.
- Todo documento lleva `document_no` único y `document_numbering_id`.
- Todo movimiento lleva `idempotency_key` único.

### Frontend

- React + TypeScript + Vite.
- Una carpeta `src/features/<dominio>/` por dominio funcional.
- Cliente API generado o tipado desde OpenAPI; no mezclar llamadas `fetch` en componentes.
- Validación de formularios con esquemas compartidos cuando sea posible.
- Sin datos sensibles en `localStorage`; tokens solo en memoria o cookie segura cuando se defina.
- UI en español, terminología técnica mínima y mensajes de error accionables.

### Commits

- Mensajes en español, imperativos y específicos: `Agrega migración inicial de esquemas`, no `cambios`.
- Un cambio lógico por commit.
- No hacer `git push --force`.
- No commitear `.env`, archivos de exportación de CONTPAQi ni dumps.

## 7. Base de datos y transacciones

- Usar `READ COMMITTED` por defecto con `SELECT ... FOR UPDATE` sobre saldos de inventario.
- Para flujos multiagregado complejos, usar `SERIALIZABLE` con reintento controlado.
- Orden determinístico de bloqueo en transferencias para evitar deadlocks.
- La auditoría y el evento de salida (`outbox`) se insertan en la misma transacción que el cambio de negocio.
- Reintentar solo errores serializables/deadlock; nunca reintentar violaciones de regla de negocio.
- Los saldos disponibles se derivan como `on_hand_qty - reserved_qty` y se validan con restricciones CHECK donde aplique.

### Invariantes de cantidades

Para cada línea de requisición:

```text
0 <= authorised_qty <= requested_qty - cancelled_qty
0 <= reserved_qty   <= authorised_qty - delivered_qty
0 <= purchased_qty  <= authorised_qty (salvo tolerancia aprobada)
0 <= received_qty   <= purchased_qty + tolerancia
0 <= delivered_qty  <= authorised_qty
```

`reserved`, `purchased`, `received` y `delivered` se calculan desde tablas de detalle (reservas, líneas de OC, recepciones y movimientos). No se aceptan valores manuales.

## 8. Seguridad

- RBAC con permisos granulares, por ejemplo `requisition.approve`, `inventory.issue`, `purchase.order.approve`.
- Alcance opcional por `company_id`, `mining_unit_id`, `department_id` y `warehouse_id`.
- La bitácora registra actor, acción, entidad, antes/después, `request_id` y correlación.
- Nunca registrar contraseñas ni tokens en logs.
- Contraseñas hasheadas con Argon2id o bcrypt mediante librería reconocida.
- La sesión y el token se configuran sin secretos embebidos.

## 9. Integraciones

### CONTPAQi Comercial Premium 11.5.1

- **Prohibido:** conexión directa a su base de datos.
- Permitido, previa autorización: importación de archivos controlados, exportaciones manuales o futuro API oficial provista por el proveedor.
- Toda carga pasa por `intg.integration_batch` → `intg.integration_staging` → validación → tablas destino.
- Cada archivo se registra por nombre, hash, tamaño, usuario y resultado.
- El ERP mantiene un espejo operativo y conciliaciones; no publica asientos contables a CONTPAQi sin aprobación.

### Sierra Madre GMAO

- No se modifica, no se escriben sus tablas, no se ejecutan scripts sobre él.
- El ERP guarda solo `external_gmao_id`, estado de sincronización y referencias.
- Cualquier intercambio futuro es vía exportación/API autorizada y queda registrado en `intg.gmao_sync_event`.

## 10. Flujo de trabajo para agentes

1. Leer este archivo y los documentos en `docs/` antes de cambiar código.
2. Verificar el estado del repositorio; si hay cambios del usuario, no sobrescribirlos.
3. Trabajar solo en el alcance de la tarea asignada.
4. Si una regla de negocio es ambigua, preguntar; no asumir.
5. Agregar o actualizar pruebas junto con el código.
6. Ejecutar las verificaciones locales disponibles.
7. Actualizar documentación solo cuando el cambio altere contratos, esquemas o decisiones.
8. Reportar claramente qué quedó pendiente. Nunca decir “terminado” si falta prueba o migración.

## 11. Comandos base (una vez creado el proyecto)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
alembic upgrade head
pytest -q
npm ci
npm run build
npm run test -- --run
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

No sustituir `127.0.0.1` por `0.0.0.0`. No publicar puertos con Docker.

## 12. Definición de terminado

Una tarea se considera terminada solo si:

- El código compila y pasa lint/type-check.
- Las pruebas nuevas y existentes pasan.
- La migración es aditiva y se probó de `empty` a `head`.
- No hay secretos ni datos reales en el diff.
- La bitácora cubre las acciones sensibles nuevas.
- La documentación relevante quedó actualizada.
- Se indican explícitamente las limitaciones y el siguiente paso.
