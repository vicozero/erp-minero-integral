# Vales de salida — formatos PDF y XLSX

## Plantilla autorizada

Se usa `docs/plantillas_referencia/VA-000162.pdf` (SHA-256 `82c868df58f06ed7df029c8a67e8239b6f73df92e95f0c8bae8b04cc8a5f6e2e`). El usuario confirmó esta plantilla el 19/11/2026: es estructuralmente idéntica a la referencia original `VA-000165` (mismo generador ReportLab, misma geometría y mismo logotipo); cambia el folio impreso y las partidas. Por decisión del usuario, **no se reprodujo el folio 165**: los vales nuevos inician en `VA-000166`.

## Estructura conservada

| Elemento | PDF | XLSX |
|---|---|---|
| Tamaño | Carta apaisada, 792 × 612 pt | Carta apaisada, `PAPERSIZE_LETTER`, orientación horizontal |
| Marco | x 12…780, y 89.7…529 pt | Área de impresión `A1:H24`, márgenes 0.2/0.4 in |
| Encabezado | Logotipo extraído de la plantilla, razón social, `VALE DE SALIDA`, `ALMACÉN`, departamento y folio | Logotipo, razón social, título, departamento y folio en celdas combinadas |
| Tabla | 8 columnas: partida, código, cantidad solicitada, unidad, descripción, cantidad despachada | Columnas A…H con combinación E:G para descripción, bordes finos |
| Paginación | 10 partidas por hoja; se conserva el diseño en cada página | Una hoja por página (`VA 1`, `VA 2`, …) con el mismo corte |
| Pie | CECO, área, uso/equipo, fecha de expedición | Fila 18/19 con las mismas etiquetas |
| Firmas | Tres recuadros: recibido, autorizado y despachado por almacén | Tres bloques combinados con `NOMBRE Y FIRMA` |

El generador está en `backend/app/modules/documentation/render_va.py`. No se ejecuta contenido de adjuntos y el XLSX no contiene fórmulas.

## Folio y trazabilidad

- Serie `VA / LAG`, **sin año**, formato `VA-000000`; secuencia inicial `166`.
- `next_document_number()` usa `year=0` como centinela de "sin año" y `start_number=166`; la asignación es atómica y queda en `doc.document_numbering`.
- Cada vale lleva `document_registry_id`, `idempotency_key`, `template_code`, `template_version`, creador, estado (`DRAFT` / `ISSUED`) y, si aplica, emisor y `issued_at`.
- Se registran eventos `VOUCHER_CREATED`, `VOUCHER_ISSUED`, `VOUCHER_RENDERED` y `VOUCHER_REPRINTED`, además de la bitácora `AuditService`.
- Cada render guarda `sha256`, tamaño, nombre lógico, plantilla, formato, actor y si es reimpresión. La reimpresión sirve **los bytes de la versión original** y referencia `source_render_id`.
- **Descargar o reimprimir no genera movimientos de stock.** El vale es un reflejo documental de entregas confirmadas, no una segunda fuente de existencias.

## Origen del vale

1. `mode=DRAFT`: partidas explícitas o partidas vigentes de una requisición autorizada. Queda marcado como borrador; `cantidad despachada` se imprime en cero.
2. `mode=DELIVERY`: requiere `requisition_id` con movimientos `ISSUE` en estado `POSTED`. Las cantidades despachadas se calculan desde esos movimientos; se vincula `stock_movement_id` cuando la partida tiene una sola entrega.

No se permite emitir un vale de entrega sin entregas confirmadas. Un vale DRAFT no se convierte en fuente de inventario: `POST /issue` solo actualiza cantidades desde los movimientos existentes.

## API

| Método | Ruta | Permiso |
|---|---|---|
| `POST` | `/api/v1/documents/vouchers` | `warehouse.voucher.create` |
| `GET` | `/api/v1/documents/vouchers` | `document.render` |
| `GET` | `/api/v1/documents/vouchers/{id}` | `document.render` |
| `POST` | `/api/v1/documents/vouchers/{id}/issue` | `warehouse.voucher.issue` |
| `GET` | `/api/v1/documents/vouchers/{id}/pdf?reprint=` | `document.render` |
| `GET` | `/api/v1/documents/vouchers/{id}/xlsx?reprint=` | `document.render` |
| `GET` | `/api/v1/documents/vouchers/{id}/renders` | `document.render` |

Todas las consultas aplican alcance por departamento; un usuario sin acceso al departamento recibe `403`. Las respuestas usan `Cache-Control: no-store` y no exponen rutas locales del servidor.

## Evidencias y validación

Ver `docs/EVIDENCIA_FORMATOS/`: PDF/XLSX sintéticos, PNG de las dos primeras páginas y reporte estructural. La validación es geométrica y de estructura (tamaño de página, paginación, celdas combinadas, área de impresión, fuentes y hashes). **No se afirma comparación píxel a píxel**; la revisión visual final sigue siendo manual con la plantilla autorizada.

## Limitaciones

- Las firmas se imprimen vacías (`NOMBRE Y FIRMA`): no se inventan nombres ni firmas.
- `CECO`, `área` y `uso/equipo` se toman de los datos de la requisición o del vale; si no se capturan, se imprimen vacíos.
- La numeración inicia en 166 por decisión del usuario; no se migra ni se reedita el folio 162/165 histórico.
- El archivo se sirve por endpoint autorizado; no existe descarga por ruta filesystem.
