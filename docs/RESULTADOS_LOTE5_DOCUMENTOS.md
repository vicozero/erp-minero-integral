# Resultados — Lote 5: documentos, vales y semáforo

**Fecha:** 19/11/2026
**Estado:** validado localmente con datos sintéticos. **No se declara producción.**
**Repositorio:** `E:\ERP_MINERO`. Sin `push`, sin despliegue, sin conexión a CONTPAQi ni GMAO.

## 1. Objetivo y punto de partida

Cerrar la cadena documental de la requisición: formatos PDF/Excel, vales de almacén, semáforo SLA y trazabilidad consultable desde el portal.

| Métrica | Antes del Lote 5 | Después del Lote 5 |
|---|---:|---:|
| Pruebas backend | 123 | **127** |
| Pruebas frontend | 32 | **41** |
| Pantallas nuevas | — | 3 (`/vales`, `/semaforo`, `/trazabilidad/:id`) |
| Endpoint de trazabilidad | — | `GET /api/v1/requisitions/{id}/trace` |

## 2. Cambios entregados

### Backend

- `documentation/service.py`: nombres nominales de recepción, autorización y despacho en el vale; proveedor recomendado derivado del proveedor preferido de `mdm.item_supplier`; datos de render para PDF/XLSX.
- `documentation/models.py` y migración aditiva `f7a8b9c0d1e2`: columnas `received_by_name`, `authorized_by_name`, `dispatched_by_name`, `signatures_recorded_at` e `signatures_recorded_by` en `doc.warehouse_voucher`. `downgrade()` lanza `RuntimeError`; no ejecutar sobre datos reales.
- `routers/documentation.py`: `POST /vouchers/{id}/signatures`, además de las descargas y el historial de renders existentes.
- `sla/service.py` y `sla/schemas.py`: campos `equipment_id` y `requester_id` en el tablero, filtros por color/estado/prioridad/departamento/equipo/responsable/fechas y cálculo de `fulfillment_percent`.
- `requisitions/service.py` y `routers/requisitions.py`: `GET /requisitions/{id}/trace` con seis etapas, autorizaciones, reservas, entregas, vales, eventos documentales y bitácora.
- `shared/constants.py`: alias `documentos.generar`, `vales.crear`, `vales.emitir`, `semaforo.consultar`, `semaforo.configurar` y `semaforo.aprobar`.

### Frontend

- `src/features/vouchers/`: generación de VA, emisión, captura de nombres, descargas PDF/Excel, reimpresión e historial de renders.
- `src/features/sla/`: tablero con totales por color, nueve columnas y ocho filtros.
- `src/features/trace/`: cadena documental de solo lectura con enlaces a los formatos.
- `src/App.tsx`, `src/components/Layout.tsx`, `src/api/client.ts`, `src/api/types.ts`: rutas, menú, métodos y tipos. Ningún componente realiza `fetch` directo.
- `src/styles.css`: estilos de los chips SLA y de la línea de tiempo documental.

## 3. Verificación ejecutada

```powershell
cd E:\ERP_MINERO\backend
python -m pytest -q
ruff check app tests
mypy app --follow-imports=silent
python -m alembic upgrade head

cd E:\ERP_MINERO\frontend
.\node_modules\.bin\tsc.cmd --noEmit
npm.cmd run test -- --run
npm.cmd run build
```

Resultados:

- Backend: **127 passed**.
- `ruff check app tests`: **All checks passed**.
- `mypy app --follow-imports=silent`: **Success: no issues found in 80 source files**.
- Alembic: revisión `f7a8b9c0d1e2` aplicada en la base de desarrollo; `head` alcanzado.
- Frontend: **41 passed**; `tsc --noEmit` sin errores; `npm run build` correcto en 2.35 s.

## 4. Validación real en el portal

Sesión autenticada en `http://localhost:5173` con la credencial de desarrollo almacenada solo en `var/secrets/admin_dev_credential.txt` (ignorada por Git; valor nunca impreso).

1. **Vales:** se generó `VA-000166` desde `REQ-LAG-2026-000003` sin crear movimientos de inventario. Se capturaron los tres nombres nominales; el portal informó explícitamente que no se generó firma gráfica.
2. **Descargas:** se obtuvieron PDF y XLSX del vale y de la requisición, con hashes registrados en `docs/evidencia/ejemplos/manifiesto_lote5.json`.
3. **Reimpresión:** el render original y la reimpresión comparten `sha256` `412c12980cc78a6f…`; se registró `VOUCHER_REPRINTED`.
4. **Emisión:** `POST /issue` devolvió `409` con «No hay entregas confirmadas para generar el vale». Es la regla de negocio esperada para un VA en modo `DRAFT`; no se alteró el inventario.
5. **Semáforo:** el tablero mostró 3 en verde, 0 amarillo, 0 rojo y 0 sin medición. El filtro `sla_color=RED` devolvió 200 con 0 filas.
6. **Trazabilidad:** la vista mostró seis etapas, dos autorizaciones, el vale vinculado, 17 eventos documentales y la bitácora con `VOUCHER_CREATE` y `VOUCHER_SIGNATURES_RECORDED`.

Evidencia visual: `docs/evidencia/01_vales.png`, `02_semaforo.png`, `03_ejemplos.png`, `04_trazabilidad.png` y `05_firmas.png`.

## 5. Lo que sí se puede generar desde el portal

- PDF y Excel de requisiciones con folio, departamento, partidas y aprobación electrónica textual cuando existe.
- PDF y Excel de vales con folio consecutivo `VA-000166` en adelante, 10 partidas por hoja y nombres nominales de quienes intervienen.
- Reimpresión que conserva bytes del último original y registra un nuevo evento de documento.
- Historial de renders con hash SHA-256, formato, actor y bandera de reimpresión.
- Tablero SLA calculado en backend, con filtros y acceso a la trazabilidad.
- Cadena documental de solo lectura requisición → autorización → reserva → entrega → vale → seguimiento.

## 6. Lo que requiere corrección o una fuente autorizada

| Pendiente | Situación actual | Acción requerida |
|---|---|---|
| Firma gráfica de las tres constancias | Solo se guardan nombres; se imprime `NOMBRE Y FIRMA` | Definir captura de firma manuscrita o firma electrónica válida y su cadena de custodia |
| Proveedor recomendado en REQ | Se toma del proveedor preferido de `mdm.item_supplier`; si no hay fuente, se imprime vacío | Confirmar cuál es el catálogo autorizado de proveedores preferidos |
| `CONSUMO MES/AÑO` en REQ | Derivado de `needed_at` | Definir fuente de consumo histórico real |
| `PROGRAMADO (ALMACEN)` y `meses_programados` | Se imprimen vacíos | Definir fuente y regla de programación de almacén |
| `USO INMEDIATO` y `CARGO OPEX` | Derivados de prioridad/tipo/centro de costo como regla de presentación | Confirmar si deben venir de un campo capturado |
| SLA en horas hábiles | Se usan horas de reloj | Definir calendario `America/Mexico_City` y días inhábiles |
| Políticas y job de SLA | Umbrales sembrados y cálculo bajo demanda; no hay pantalla de configuración ni evaluación automática | Definir UI de políticas, periodicidad y notificaciones |
| Área del VA en PDF | El diseño autorizado trunca a 12 caracteres; el XLSX conserva el texto completo | Validar si se amplía el diseño o se acepta el límite de la plantilla |
| Emisión de VA sin entregas | Bloqueada con `409` por diseño | Surtir primero desde Almacén; no es un defecto |

## 7. Cadena de custodia

- Cada descarga crea un `DocumentRender` con hash, tamaño, plantilla, formato, actor y bandera de reimpresión.
- Los eventos documentales y la auditoría se insertan en la misma transacción que el cambio de negocio.
- `issue_voucher` y las descargas no crean movimientos; las pruebas comparan el kardex antes y después.
- La bitácora conserva actor, acción, entidad, timestamp y `request_id`; la tabla tiene el trigger de inmutabilidad.

## 8. Limitaciones y siguiente paso

No hubo notificaciones, escalamiento, integración externa ni exposición de red. La comparación de formatos es geométrica y estructural, no píxel a píxel. La credencial administrativa no se versiona.

Siguiente paso: capturar firma válida y fuente de consumo/programación/proveedor preferido; después definir el job y la pantalla de políticas SLA. Cualquier cambio de esquema debe seguir siendo aditivo y estar acompañado por pruebas.
