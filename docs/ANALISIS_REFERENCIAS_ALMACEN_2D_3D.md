# Análisis de referencias visuales — Almacén virtual 2D/3D (Lote 6)

**Fecha:** 19/11/2026
**Directorio analizado:** `docs/plantillas_referencia/`
**Método:** lectura de metadatos y hashes, OCR de las capas de texto, cuantización de paleta, densidad de bordes y detección de líneas con OpenCV.
**Limitación metodológica:** el modelo que ejecuta este proyecto no dispone de entrada visual directa para imágenes. Las conclusiones sobre composición y perspectiva se infieren de OCR y métricas de píxel; **no se afirma una comparación visual pixel a pixel**. Antes de aprobar el diseño definitivo, el usuario debe confirmar las capturas reales del portal indicadas en el Lote 6.

## 1. Regla de integridad

No se eliminó, renombró, reemplazó ni modificó ninguna imagen original. Todas las referencias siguen en su carpeta y se identifican por su nombre original y SHA-256 (prefix de 16 caracteres). Ninguna imagen se copió al código ni se publica en la API.

## 2. Inventario de archivos gráficos

| Archivo | Formato | Dimensiones | SHA-256 (16) | Clasificación inferida |
|---|---|---:|---|---|
| `0b37f76a-8099-499c-a196-dd663c0c0c0f.png` | PNG | 1672×941 | `aef01e3f1b346647` | 2D · editor del plano, con racks A–E y herramientas |
| `46ee354f-920f-47af-a674-45d486c3bd2d.png` | PNG | 1672×941 | `4f95614d1c58cd09` | 2D · dashboard general con zonas, KPIs y alertas |
| `4e3878ec-a475-4a9a-a4ad-11aeeaa52213.png` | PNG | 1672×941 | `6ec1a04950c22952` | 2D · mapa de ubicaciones e inventario por ubicación |
| `ddcdf2de-4bae-4349-b98b-9385b32cfe22.png` | PNG | 1672×941 | `6ec1a04950c22952` | **Idéntico byte a byte** al anterior |
| `503c393d-3e95-4ca5-a847-ef7e5a41d07b.png` | PNG | 1672×941 | `2114b2c06ca0b918` | 2D · plano + lista filtrable de ubicaciones |
| `603227b9-0832-4a09-9cd5-53a6b84802d6.png` | PNG | 1672×941 | `88b181a0021ba6bb` | 2D · mapa + detalle de ubicación y movimientos |
| `934481d4-b7b1-40c5-927d-acc7ccba50dc.png` | PNG | 1672×941 | `7fe7a585cf501a06` | 2D · mapa con ruta de surtido |
| `de8a842f-bcbc-4acb-8d4a-b0611017ef60.png` | PNG | 1672×941 | `b9f45f3c7bcb426c` | 2D/3D incierto · vista de racks en diagonal y árbol de ubicaciones |
| `e28c4ced-6841-462c-824f-78c447afbbb3.png` | PNG | 1672×941 | `5106dc59d9ed74e8` | 3D · «Digital Twin» con capas y semáforo de ocupación |
| `Sin título.png` | PNG | 685×431 | `e8ab5cec0692ca3b` | 2D · paleta de plantillas de rack/zona con rejilla |
| `3M1WtPpl…jfif` | JFIF | 830×470 | `43dd639dab1f666e` | 2D · visualización estructural Entersoft WMS |
| `SKJbVFOQ…jfif` | JFIF | 1854×860 | `397c9b75efbd5dc9` | 3D · Warehouse Control Tower, pasillos y bins |
| `n2tpLFnUe…jfif` | JFIF | 1536×1024 | `8ca5111ebb8ca08b` | 3D · dashboard digital twin con heatmap |
| `xi-2iirf…jfif` | JFIF | 1024×904 | `9ab482da7b02c274` | 2D · cuadrícula ortogonal `A15…P01`, `Grid=10ft` |

Los dos PDF (`VA-000162.pdf`, `Requisicion_REQ-0006_…pdf`) pertenecen al Lote 5 y no intervienen en este análisis.

## 3. Hallazgos por familia

### Familia A — mockups «Almacén Virtual» (9 PNG de 1672×941)

Comparten cabecera azul marino, barra lateral del ERP, pestañas `Vista 2D (Plano)` / `Vista 3D (Digital Twin)` / `Listado de ubicaciones` / `Ocupación`, y la codificación jerárquica `Zona-Rack-Nivel-Posición` (`A-01-02-03`). Aparecen pasillos `A…E`, zonas de recepción, control de calidad, cuarentena, despacho, EPP y refacciones críticas.

Elementos recurrentes detectados por OCR:

- KPIs: total de ubicaciones, ocupación global (78 % en los mockups), artículos, stock crítico, requisiciones abiertas y valor de inventario.
- Semáforo de ocupación: verde `0–69 % Disponible`, ámbar `70–89 % Ocupación media`, rojo `90–100 % Alta ocupación`, gris `Inactiva/Bloqueada`.
- Panel lateral: jerarquía, capacidad, existencia, % ocupación, estado, pestañas `Inventario / Movimientos / Historial`, QR y acciones.
- `e28c4ced` declara explícitamente `Vista 3D (Digital Twin)`, `Capas`, `Mostrar etiquetas` y `Reubicar (Arrastrar y soltar)`.
- `934481d4` muestra una ruta de surtido `Recepción → A-01-04 → C-01-03 → D-01-04 → Despacho`, con distancia y tiempo estimados.
- `0b37f76a` muestra la barra de herramientas de edición: seleccionar, agregar rack/zona/pasillo, editar, coordenadas X/Y, deshacer/rehacer, guardar plano.

Los valores numéricos de los mockups no son uniformes (426 vs 1 600 ubicaciones, importes distintos, e incluso `Mina San Pedro` en `de8a842f`). **No se tomaron como datos reales ni como contrato**: las cantidades del Lote 6 vendrán de `inv.stock_balance` y `mdm.storage_location`.

### Familia B — digital twin externo (JFIF)

`SKJbVFOQ` y `n2tpLFnUe` muestran racks en perspectiva con pasillos etiquetados, contenedores dentro de los racks, zonas de circulación y capas de calor. Su paleta es oscura (azul noche / olivo). Aportan la idea de **capas conmutables** y de distinguir visualmente estructura, stock y área libre, no un esquema de colores obligatorio.

### Familia C — editores de rejilla (2D)

`Sin título.png` muestra plantillas paramétricas (`Bin Organizer 18×13×12`, `Flow Rack 96×48×72`, `Double-Deep Pallet Rack`, `Standard Pallet Rack`) y tipos de zona (`Aisle`, `Staging Area`, `DockDoor`, `Wall`, `Office`) con `Grid: 100x80 · Cell: 6"`. `xi-2iirf` muestra una rejilla `Grid=10ft, Snap=1ft`. `3M1WtPpl` muestra pasillos `A01…A04` y campos `Fullness`, `Quantity (containers)` y códigos de posición.

## 4. Elementos que se implementarán

| Elemento de referencia | Implementación en el Lote 6 | Fuente de datos |
|---|---|---|
| Plano superior con racks, pasillos y zonas | Vista 2D interactiva con zoom, desplazamiento y resaltado | `GET /api/v1/wms/maps/{warehouse_id}` (nodos derivados de `mdm.storage_location`) |
| Semáforo de ocupación | Leyenda y colores configurables por ocupación (0–69 / 70–89 / 90–100 / bloqueada) | `occupied_qty` / `capacity_qty` reales |
| Codificación `Zona-Rack-Nivel-Posición` | Jerarquía agrupada para construir la escena 3D | `zone`, `aisle`, `rack`, `level`, `position` |
| Vista 3D con capas y etiquetas | Escena React Three Fiber con piso, pasillos, racks, niveles, posiciones y cajas ilustrativas | Misma jerarquía WMS; geometría referencial configurable |
| Rotar / zoom / mover / restablecer cámara | `OrbitControls` + botón de reinicio | Cliente |
| Panel `Inventario / Movimientos / Historial` | Panel lateral con cantidades físicas, disponibles y reservadas, número de parte, UOM, último movimiento y restricciones | `GET /api/v1/wms/locations/{id}/inventory` |
| Costo restringido | Campo de costo solo para roles con `warehouse.stock.view` | Misma respuesta, omitido para otros perfiles |
| KPIs y alertas | Dashboard con filtros por almacén, zona y familia | `GET /api/v1/wms/dashboard` |
| Búsqueda de refacciones | Buscador que devuelve ubicaciones coincidentes y las resalta en 2D y 3D | `GET /api/v1/wms/materials/search` |
| Advertencia de plano referencial | Se conserva la etiqueta `is_exact=false` y el aviso permanente | `wms.location_map` (sin cambios de esquema) |
| Historial de versiones | Se conserva el selector de versiones existente | Endpoints existentes |

## 5. Decisiones de diseño

1. **No se crearán racks ficticios.** Cada rack, nivel y posición dibujado en 3D corresponde a una fila existente de `mdm.storage_location`. Si una ubicación no tiene coordenadas, se lista como «sin ubicar en el plano» y no se inventa una posición.
2. **Geometría referencial.** El proyecto no dispone de medidas físicas verificadas de la bodega. Las dimensiones de piso, rack, nivel y caja son parámetros ajustables en la interfaz, rotulados como «geometría referencial, no medida física». No se deduce escala real de las imágenes.
3. **Estados distintos.** Estado de ubicación (`ACTIVE/BLOCKED/INACTIVE`), ocupación (porcentaje de capacidad definida) y stock bajo mínimo (comparación contra `reorder_point`/`safety_stock`) se calculan y muestran por separado.
4. **Sin efectos de inventario.** Ninguna interacción gráfica modifica saldos. La edición persistente se limita a coordenadas y metadatos del plano, ya auditados por el servicio existente.
5. **Fallback 2D.** Si WebGL no está disponible, la vista 3D muestra un mensaje y deja la vista 2D como alternativa funcional.
6. **Dependencias fijadas.** React 18.3.1 → `@react-three/fiber@8.18.0` y `@react-three/drei@9.122.0` (peers `react >=18 <19`, `three >=0.137`), con `three@0.169.0`. La rama v9 de Fiber exige React 19 y no se usa.

## 6. Fuente de las cantidades

Toda cantidad mostrada proviene de `inv.stock_balance` (`on_hand_qty`, `reserved_qty`, `available_qty = on_hand - reserved`) y de los movimientos registrados en `inv.stock_movement`. El campo `occupied_qty` de los nodos se agrega en backend desde saldos; el cliente no calcula existencias a partir de colores ni de imágenes.

## 7. Siguiente fase

Con este inventario como entrada se extienden los endpoints WMS y se construyen las vistas 2D y 3D sobre la jerarquía real, conservando el sistema de versiones y la advertencia de plano referencial.
