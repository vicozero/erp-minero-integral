# Requisiciones de compra — formatos PDF y XLSX

## Plantilla autorizada

Se usa la versión **Carta** del escritorio (612 × 792 pt), productor `Nitro PDF Pro 14`, copiada a `docs/plantillas_referencia/Requisicion_REQ-0006_JL-03_2026-11-13.pdf` con SHA-256 `5df7f95ee6d850f2b067708a40AD6EA4551C47A7DD2578A3519BDE4800526062`. El usuario la eligió el 19/11/2026 sobre una copia A4 generada por Excel que también estaba en la raíz.

> Nota: la capa de texto de la plantilla contiene `REQUISICION No.` pero **no expone el valor del folio**; por eso se valida que el folio del documento generado aparezca en la salida, no que coincida con un texto extraíble de la referencia.

## Estructura conservada

| Elemento | PDF | XLSX |
|---|---|---|
| Tamaño | Carta vertical, 612 × 792 pt | Carta vertical, orientación portrait |
| Marco | x 14.9…596.6, y 101.2…698.2 pt | Área de impresión `A1:P38` |
| Encabezado | Logotipo extraído, razón social, `DIA / MES / AÑO`, mina, `REQUISICIÓN DE COMPRA`, `REQUISICION No.` | Logotipo, razón social, fecha, mina, folio |
| Control | `DEPTO. SOLICITANTE`, `USO INMEDIATO`, `EXISTENCIA ALMACEN`, `CARGO OPEX` | Mismo bloque en filas 3–4 |
| Tabla | 21 partidas por hoja: partida, cantidad, unidad, descripción, consumo mes/año, existencia, codificación | Una hoja por página (`REQ 1`, `REQ 2`, …) con columnas editables |
| Meses | `REQUERIDO PARA` y `PROGRAMADO (ALMACEN)` con ENE…DIC | Filas de months en el bloque inferior |
| Pie | `USO`, `PROVEEDOR RECOMENDADO` y tres firmas | Bloques inferiores con `FIRMA SOLICITANTE`, `FIRMA JEFE DE ALMACEN`, `AUTORIZACION GERENCIA` |
| Tipografía | Calibri / Calibri Bold si están disponibles; si no, Helvetica | Calibri |

El generador está en `backend/app/modules/documentation/render_req.py`. No hay fórmulas en el XLSX y no se ejecuta contenido de archivos adjuntos.

## Datos y firmas

- El folio, departamento, mina, fecha y partidas se toman de la requisición existente (módulo `req`); **no se crea un documento paralelo**.
- `USO INMEDIATO` se marca cuando la prioridad es `HIGH` o `URGENT`; `EXISTENCIA ALMACEN` cuando el tipo es `STOCK`; `CARGO OPEX` cuando hay centro de costo. Son reglas de presentación del formato, no cambian el estado administrativo.
- `CONSUMO MES/AÑO` se deriva de `needed_at`, porque hoy no existe una fuente de consumo histórico confiable. Si no hay fecha requerida, se imprime vacío.
- `PROVEEDOR RECOMENDADO` se deriva del proveedor preferido de `mdm.item_supplier` del primer artículo con proveedor conocido. Si no hay fuente, se imprime vacío; no se inventa un proveedor.
- `PROGRAMADO (ALMACEN)` y `meses_programados` se imprimen vacíos mientras no exista una fuente de datos autorizada. No se inventan valores.
- Las tres firmas quedan en blanco. Cuando la requisición tiene `approved_at`, se añade bajo autorización gerencial el texto `[Aprobación electrónica: ESTADO YYYY-MM-DD HH:MM]`. Esa marca es informativa y auditables: la decisión real vive en los eventos de aprobación y en la bitácora del flujo de autorización por partida.

## API

| Método | Ruta | Permiso |
|---|---|---|
| `GET` | `/api/v1/documents/requisitions/{id}/pdf?reprint=` | `document.render` |
| `GET` | `/api/v1/documents/requisitions/{id}/xlsx?reprint=` | `document.render` |
| `GET` | `/api/v1/documents/requisitions/{id}/renders` | `document.render` |

El acceso aplica `assert_department_access`: un usuario fuera del departamento recibe `403`. Descargar no modifica la requisición, no cambia autorizaciones y no genera movimientos de inventario. La reimpresión sirve la versión previamente emitida y registra un nuevo `DocumentRender` con `is_reprint=true`.

## Evidencias y validación

Ver `docs/EVIDENCIA_FORMATOS/`. Se validan tamaño de página, número de páginas, paginación de 21 partidas, área de impresión, combinaciones de celdas, fuentes y hashes. No se afirma comparación píxel a píxel.

## Limitaciones

- No se captura firma gráfica; solo se distingue la aprobación electrónica por texto y por su registro en el flujo.
- La plantilla de referencia no incluye el folio en texto extraíble; la comprobación se hace sobre el PDF generado.
- Los fondos PNG del almacén virtual no intervienen en este formato.
