# Validación de formatos PDF y Excel — Lote 5

**Fecha:** 19/11/2026
**Alcance:** validación estructural y descarga real desde el portal de los formatos de requisición y vale de almacén.
**Datos:** 100 % sintéticos. No se usaron documentos reales de CONTPAQi ni de la unidad.

## 1. Plantillas autorizadas

| Formato | Referencia | SHA-256 de la plantilla | Decisión |
|---|---|---|---|
| Vale de salida | `docs/plantillas_referencia/VA-000162.pdf` | `82c868df58f06ed7df029c8a67e8239b6f73df92e95f0c8bae8b04cc8a5f6e2e` | Estructuralmente idéntica a `VA-000165`; el usuario autorizó iniciar en `VA-000166` |
| Requisición | `docs/plantillas_referencia/Requisicion_REQ-0006_JL-03_2026-11-13.pdf` | `5df7f95ee6d850f2b067708a40AD6EA4551C47A7DD2578A3519BDE4800526062` | Versión Carta/Nitro, preferida sobre la copia A4/Excel |

La referencia original `VA-000165.pdf` no se copió al repositorio.

## 2. Ejemplos generados desde el portal

| Archivo | Bytes | SHA-256 | Comprobación |
|---|---:|---|---|
| `VA-000166.pdf` | 53 611 | `89E27D855DAC7A64442AD1C9D93B613439456479CBC094EFE9BEF604C7C80FD1` | Texto extraído: folio, 2 partidas, CECO, área, uso/equipo, fecha y tres nombres nominales |
| `VA-000166.xlsx` | 48 185 | `F457DA798B8A4A9547856069F9AFBC0A0DCC958E2456A5CCA485DA132E55587A` | 24 filas × 8 columnas, área `A1:H24`, nombres completos y sin fórmulas |
| `REQ-LAG-2026-000003.pdf` | 70 060 | `65618066DDA3E79A9A5C2EB1211F9214843BFDE9FFA827C9612EAF7774F6E1EB` | Carta vertical, folio presente en la capa de texto |
| `REQ-LAG-2026-000003.xlsx` | 15 001 | `4F7612C0D84FC2FDE2261A86A4D0648F81C84B5E1320F642FD949811B0C6737B` | Hojas por página, área de impresión conservada y sin fórmulas |

Ubicación: `docs/evidencia/ejemplos/`. Manifiesto consolidado: `docs/evidencia/ejemplos/manifiesto_lote5.json`.
Capturas del portal: `docs/evidencia/01_vales.png`, `02_semaforo.png`, `03_ejemplos.png`, `04_trazabilidad.png`, `05_firmas.png`.

## 3. Comprobaciones del vale

- **Geometría:** Carta apaisada `792 × 612 pt`; marco y tabla conservados de la plantilla.
- **Paginación:** 10 partidas por hoja, con relleno de filas vacías numeradas hasta 10.
- **Columnas:** partida, código, cantidad solicitada, unidad, descripción y cantidad despachada.
- **Origen de cantidades:** `dispatched_qty` se deriva de movimientos `ISSUE` confirmados; en el ejemplo sintético es `0` porque el vale está en `DRAFT`.
- **Firmas:** se imprimen los nombres capturados y la leyenda `NOMBRE Y FIRMA`. No se dibuja ni falsifica una firma gráfica.
- **Exportación:** el XLSX conserva el texto completo del campo `Área`; el PDF respeta el límite de 12 caracteres del diseño autorizado (`SINTETICO-LOTE5` → `SINTETICO-LO`).
- **Sin efectos secundarios:** descargar no cambia existencias, reservas ni autorizaciones; las pruebas comparan el kardex antes y después.

## 4. Comprobaciones de la requisición

- **Geometría:** Carta vertical `612 × 792 pt`; 21 partidas por página.
- **Datos:** folio, departamento, mina, fecha y partidas se leen de la requisición existente; no se crea un documento paralelo.
- **Aprobación:** cuando existe `approved_at`, se añade una marca textual de aprobación electrónica. La decisión real está en los eventos del flujo.
- **Proveedor recomendado:** se deriva del proveedor preferido en `mdm.item_supplier` del primer artículo con proveedor conocido. Si no hay fuente, se imprime vacío; no se inventa un proveedor.
- **Campos derivados:** `CONSUMO MES/AÑO` sale de `needed_at`; `USO INMEDIATO`, `EXISTENCIA ALMACEN` y `CARGO OPEX` son reglas de presentación basadas en prioridad, tipo y centro de costo.
- **Pendiente de fuente:** `PROGRAMADO (ALMACEN)` y `meses_programados` permanecen vacíos.

## 5. Reimpresión y cadena de custodia

El historial del vale `VA-000166` mostró un render original de PDF con `sha256` `412c12980cc78a6f…` y una reimpresión con el **mismo hash**. El evento `VOUCHER_REPRINTED` quedó registrado con `source_render_id`.

Las descargas frescas posteriores a la captura de nombres generaron nuevos renders (`89e27d85…` para PDF y `f457da79…` para XLSX), ya que el servicio vuelve a renderizar cuando `reprint=false`. Es el comportamiento esperado: la reimpresión preserva la última versión original; la descarga fresca reflecta los nombres capturados.

Cada render registra `sha256`, tamaño, plantilla, formato, actor, timestamp e indicador de reimpresión. Las respuestas HTTP usan `Cache-Control: no-store` y `X-Content-Type-Options: nosniff`.

## 6. Método de validación

1. Descarga autorizada desde el portal con la sesión de desarrollo.
2. Extracción de texto con `pypdf` y lectura de celdas con `openpyxl`.
3. Comparación de hashes con `Get-FileHash -Algorithm SHA256`.
4. Revisión de eventos y renders vía `/api/v1/documents/vouchers/{id}/renders` y `/api/v1/requisitions/{id}/trace`.

**No se afirma comparación píxel a píxel.** La validación es estructural y de contenido; la revisión visual definitiva contra la plantilla autorizada sigue siendo manual.

## 7. Limitaciones

- No se captura firma gráfica ni se valida una firma electrónica.
- El PDF del VA trunca `Área` a 12 caracteres por el diseño de la plantilla.
- La capa de texto de la plantilla REQ no expone el folio; la comprobación se hace sobre el documento generado.
- La plantilla REQ usa columnas de meses simplificadas; no es una réplica celda por celda.
- Los PNG del almacén no intervienen en estos formatos.
