# Inspección técnica de plantillas PDF — Fase 0

> Fecha: 2026-11-19  
> Método: extracción de capa de texto, imágenes incrustadas y trazos vectoriales con PyMuPDF y pdfplumber.  
> Limitación: el modelo no dispone de entrada visual de imagen/PDF en esta sesión, por lo que **no se realizó una comparación pixel a pixel**.Las posiciones provienen de coordenadas reales extraídas del PDF, no de estimaciones visuales.

---

## 1. Archivos inspeccionados

| Rol | Archivo | Ubicación encontrada (fuera del repo) |
|---|---|---|
| Vale de salida | `VA-000165.pdf` | `C:\Users\Dell\Desktop\mantenimiento\vales\VA-000165.pdf` |
| Requisición de compra | `Requisicion_REQ-0006_JL-03_2026-11-13.pdf` | `C:\Users\Dell\Desktop\Requisicion_REQ-0006_JL-03_2026-11-13.pdf` |

Ninguno de los dos está actualmente en `E:\ERP_MINERO`. La carpeta `docs/plantillas_referencia/` queda preparada para que el usuario los copie.

---

## 2. VA-000165.pdf

### 2.1 Geometría

| Propiedad | Valor |
|---|---|
| Páginas | 1 |
| Orientación | Apaisada (landscape) |
| Tamaño | 792.0 × 612.0 pt |
| Tamaño mm | 279.4 × 215.9 mm (carta apaisada) |
| Rotación | 0° |
| Trazos vectoriales | 89 |
| Imágenes incrustadas | 1 |
| Productor | ReportLab PDF Library |
| Título incrustado | `Vale de salida - VA-000131` (no coincide con el folio impreso) |

### 2.2 Márgenes y caja de texto

| Borde | Coordenada aproximada |
|---|---|
| Izquierdo | x = 11.9 pt |
| Derecho | x = 775.1 pt; margen derecho ≈ 16.9 pt |
| Superior | y = 88–91 pt |
| Inferior | y = 521.6 pt; margen inferior ≈ 90.4 pt |
| Marco de trazos | x = 12.0..780.0, y = 89.7..529.0 |

### 2.3 Logotipo

- Imagen incrustada `xref=3`, 444 × 202 px.
- Ubicación: x = 47.8..195.8, y = 96.1..163.4 pt.
- Se conserve como imagen del documento; no se redibuje.

### 2.4 Encabezado

Texto extraído, con posiciones aproximadas:

| Elemento | y (pt) | x (pt) | Texto |
|---|---:|---:|---|
| Razón social | 88 | 244..539 | `LA GUITARRA COMPAÑÍA MINERA SA DE CV` |
| Etiqueta folio | 88 | 649..693 | `F O L I O` (letras espaciadas) |
| Título | 112 | 336..409 | `VALE DE SALIDA` |
| Subtítulo | 128 | 374 | `ALMACÉN` |
| Folio | 128 | 635 | `VA-000165` |
| Departamento | 144 | 270 / 446 | `DEPARTAMENTO:` / `MANTENIMIENTO` |

### 2.5 Tabla de partidas

- Una tabla detectada de **21 filas × 8 columnas**.
- El encabezado ocupa aproximadamente y = 176..192.
- Columnas, según texto y posiciones:

| Columna | x aproximado | Encabezado |
|---|---:|---|
| 1 | 12 | `PARTIDA` |
| 2 | 69 | `CÓDIGO` |
| 3 | 124–151 | `CANT. SOLICITADA` |
| 4 | 189 | `UNIDAD` |
| 5 | 350–553 | `D E S C R I P C I Ó N D E M A T E R I A L` |
| 8 | 707–716 | `CANTIDAD DESPACHADA` |

- **10 partidas por hoja**. Filas detectadas en y ≈ 208, 224, 240, 256, 280, 296, 312, 328, 344 y 368.
- El original tiene contenido solo en las partidas 1–5; las filas 6–10 quedan vacías pero con borde.

### 2.6 Pie de datos y firmas

| Elemento | y (pt) | Texto / posición |
|---|---:|---|
| Etiquetas | 400 | `CECO:` x=52, `ÁREA:` x=162, `USO/EQUIPO:` x=294, `FECHA DE EXPEDICIÓN:` x=543 |
| Valores | 424–432 | `MANTENIMIENTO`, `ST-24-CARGADOR SANDVIK LH-307 -`, `CARGADOR SANDVIK LH-307 # 24`, `17/11/2026` |
| Títulos de firma | 448 | `RECIBIDO POR:` x=85, `AUTORIZADO POR:` x=281, `DESPACHADO POR ALMACÉN:` x=527 |
| Línea de firma | 504 | `NOMBRE Y FIRMA` bajo cada bloque (x≈76, 280, 554) |

No se detectaron firmas manuscritas ni nombres en los espacios de firma: son líneas/espacios en blanco.

---

## 3. Requisicion_REQ-0006_JL-03_2026-11-13.pdf

### 3.1 Geometría

| Propiedad | Valor |
|---|---|
| Páginas | 1 |
| Orientación | Vertical (portrait) |
| Tamaño | 612.0 × 792.0 pt |
| Tamaño mm | 215.9 × 279.4 mm (carta) |
| Rotación | 0° |
| Trazos vectoriales | 74 |
| Imágenes incrustadas | 1 |
| Productor | Nitro PDF Pro 14 |

### 3.2 Márgenes y caja de texto

| Borde | Coordenada aproximada |
|---|---|
| Izquierdo | x = 16.4 pt |
| Derecho | x = 585.5 pt; margen derecho ≈ 26.5 pt |
| Superior | y = 58.3 pt (logotipo) / 73.0 pt (texto) |
| Inferior | y = 712.7 pt; margen inferior ≈ 79.3 pt |
| Marco de trazos | x = 14.9..596.6, y = 101.2..698.2 |

### 3.3 Logotipo

- Imagen incrustada `xref=11`, 148 × 67 px.
- Ubicación: x = 14.9..84.1, y = 58.3..89.9 pt.
- Razón social a la derecha: `LA GUITARRA COMPAÑÍA MINERA S.A. DE C.V.` en y ≈ 72, x = 215..466.

### 3.4 Encabezado

| Elemento | y (pt) | x (pt) | Texto |
|---|---:|---:|---|
| Fecha | 104–120 | 24 / 54 / 86 | `DIA` / `MES` / `AÑO`; valores `13` / `11` / `2026` |
| Mina | 104 | 226..276 | `MINA LA GUITARRA` |
| Folio | 104–107 | 497..538 | `REQUISICION No.` |
| Título | 120 | 210..301 | `REQUISICIÓN DE COMPRA` |

**Folio:** la capa de texto contiene la etiqueta `REQUISICION No.` pero **no contiene el valor**. El nombre del archivo sugiere `REQ-0006`, pero ese dato no se confirma en el texto extraído; no debe asumirse como valor del documento sin revisión visual del original.

### 3.5 Bloques de cabecera

Segunda tabla detectada (2 filas × 5 columnas):

| Elemento | y (pt) | Texto |
|---|---:|---|
| Departamento | 144–160 | `DEPTO. SOLICITANTE:` / `MTTO` |
| Uso inmediato | 144 | `USO INMEDIATO` con `X` en x≈429 |
| Existencia | 160 | `EXISTENCIA ALMACEN` |
| Cargo | 152–160 | `CARGO` / `OPEX` |

### 3.6 Tabla principal de partidas

- Tercera tabla detectada: **29 filas × 16 columnas**.
- Dos primeras filas de encabezado:
  - y ≈ 184–192: `PARTIDA`, `CANTIDAD`, `UNIDAD`, `DESCRIPCION`, `CONSUMO`, `EXIST.`, `CODIFICACION`.
  - y ≈ 200: subencabezado `MES` / `AÑO` dentro de `CONSUMO`.
- **21 partidas por hoja**, en y ≈ 216..496 con paso de ~16 pt.
- Columnas principales por posición:

| Columna | x aproximado |
|---|---:|
| PARTIDA | 18–28 |
| CANTIDAD | 47–59 |
| UNIDAD | 82–88 |
| DESCRIPCION | 216–256 |
| CONSUMO MES / AÑO | 457 / 484 |
| EXIST. | 509 |
| CODIFICACION | 542 |

- El original contiene 21 partidas reales; no hay filas vacías en el cuerpo principal.

### 3.7 Bloques posteriores

| Elemento | y (pt) | Posición / texto |
|---|---:|---|
| `REQUERIDO PARA:` | 512 | x=34; meses `ENE` x=122, `FEB` x=161, `MAR` x=197, `ABR` x=236, `MAY` x=273, `JUN` x=312, `JUL` x=351, `AGO` x=387, `SEP` x=426, `OCT` x=458, `NOV` x=484, `DIC` x=513 |
| `PROGRAMADO (ALMACEN):` | 528 | x=20 |
| `USO:` | 552 | x=55; valor `JL-03 JUMBO MUKI` en x=319..367 |
| `PROVEEDOR RECOMENDADO:` | 584 | x=18, sin valor en la capa de texto |
| Firmas | 704 | `FIRMA SOLICITANTE` x=45, `FIRMA JEFE DE ALMACEN` x=254, `AUTORIZACION GERENCIA` x=477 |

No se detectaron nombres ni firmas manuscritas en los tres bloques de firma; aparecen como espacios en blanco para firma.

---

## 4. Elementos obligatorios detectados para los generadores

### Vale de salida

- Cabecera: razón social, logotipo, `VALE DE SALIDA / ALMACÉN`, folio `VA-######`, departamento.
- Tabla: 10 partidas con PARTIDA, CÓDIGO, CANT. SOLICITADA, UNIDAD, DESCRIPCIÓN DE MATERIAL, CANTIDAD DESPACHADA.
- Pie: CECO, ÁREA, USO/EQUIPO, FECHA DE EXPEDICIÓN.
- Firmas: RECIBIDO POR, AUTORIZADO POR, DESPACHADO POR ALMACÉN; texto `NOMBRE Y FIRMA`.
- Formato: carta apaisada.

### Requisición de compra

- Cabecera: razón social, logotipo, DIA/MES/AÑO, MINA LA GUITARRA, folio, título.
- Bloques: DEPTO. SOLICITANTE, USO INMEDIATO, EXISTENCIA ALMACEN, CARGO OPEX.
- Tabla: 21 partidas con PARTIDA, CANTIDAD, UNIDAD, DESCRIPCION, CONSUMO MES/AÑO, EXIST., CODIFICACION.
- Bloques posteriores: REQUERIDO PARA (12 meses), PROGRAMADO (ALMACEN), USO, PROVEEDOR RECOMENDADO.
- Firmas: FIRMA SOLICITANTE, FIRMA JEFE DE ALMACEN, AUTORIZACION GERENCIA.
- Formato: carta vertical.

---

## 5. Decisiones que requieren el PDF original

1. Copiar las dos plantillas a esta carpeta y confirmar que no contienen datos reales que deban anonimizarse antes de versionarse.
2. Revisar visualmente el valor del folio de la requisición; no aparece en la capa de texto.
3. Confirmar si las firmas y logotipos deben conservarse exactamente como imagen o redibujarse como vectores/plantilla.
4. Definir el tipo documental del vale (`VALE` o equivalente) en `DOCUMENT_TYPES` y su serie de numeración.
5. Definir la política de SLA/semáforo antes de implementar cálculos.
