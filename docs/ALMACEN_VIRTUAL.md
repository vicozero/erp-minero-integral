# Almacén virtual — jerarquía, plano 2D y QR

**Fecha:** 19/11/2026
**Estado:** implementado y probado localmente (Lote 3 del plan WMS). No apto para producción.
**Autoridad:** `AGENTS.md`, `docs/WMS_REGLAS_NEGOCIO.md` (UB-007, UB-010) y `docs/WMS_MODELO_DATOS.md`.

---

## 1. Decisiones aprobadas

| Tema | Decisión |
|---|---|
| Fuente de posiciones | `mdm.storage_location`. El plano se proyecta desde coordenadas; la tabla del mapa nunca guarda nodos. |
| Fondo 2D | Proyección + fondo opcional. Sin imagen por defecto. Si se carga, se etiqueta siempre `Referencial · no es plano exacto`. |
| Imágenes de plantillas | No se usa ningún PNG de `docs/plantillas_referencia/` como plano. |
| Exactitud | `LocationMap.is_exact` queda forzado a `false` por `CHECK`. Ninguna imagen se presenta como plano exacto. |
| Tokens QR | Los tokens nuevos son opacos `WMS-…`. Los legados `WMS:ALM…` de la semilla no se reescriben. |
| Permisos | Consulta `warehouse.map.view`; administración `warehouse.map.manage`. El backend es la autoridad. |
| Escala | El plano es una proyección referencial; no sustituye la verificación física ni es fuente de existencias. |

---

## 2. Modelo y migración

### `e5f6a7b8c9d0` (aditiva, desde `d2e3f4a5b6c7`)

- Crea el esquema `wms`.
- Agrega `mdm.storage_location.coord_x` y `coord_y` `NUMERIC(12,4)` nullable, con
  `ck_storage_location_coordenadas`: ambas o ninguna. Índice por almacén y coordenadas.
- Crea `wms.location_map`, versionado por almacén:

| Columna | Uso |
|---|---|
| `map_version` | Versión secuencial por almacén (`uq_location_map_version`). |
| `label` | Texto visible de no exactitud. |
| `background_path`, `background_name`, `background_sha256` | Fondo opcional y su huella. |
| `is_exact` | Siempre `false` por `ck_location_map_no_exacto`. |
| `width`, `height` | Lienzo en unidades del plano; acotan las coordenadas. |
| `is_active` | Una sola versión activa por almacén (índice parcial). |
| `notes` | Observaciones libres. |

- Siembra la versión 1 para los almacenes existentes. No hay `downgrade`: la migración lo bloquea.

### Jerarquía

`build_location_path()` deriva en backend:

```text
unidad / almacén / zona / pasillo / rack / nivel / posición / código
```

Es una cadena calculada, no un dato independiente. `parent_id` de `mdm.storage_location`
representa la relación jerárquica y se valida al crear: debe existir, pertenecer al mismo
almacén y no formar ciclos.

---

## 3. API (`/api/v1/wms`)

| Método | Ruta | Permiso | Uso |
|---|---|---|---|
| `GET` | `/maps/{warehouse_id}` | `warehouse.map.view` | Versión activa + nodos proyectados. |
| `GET` | `/maps/{warehouse_id}/versions` | `warehouse.map.view` | Historial de versiones. |
| `PATCH` | `/maps/{warehouse_id}` | `warehouse.map.manage` | Crea nueva versión de metadatos. |
| `POST` | `/maps/{warehouse_id}/background` | `warehouse.map.manage` | Crea versión con fondo validado. |
| `GET` | `/maps/{warehouse_id}/background?version=N` | `warehouse.map.view` | Sirve el fondo de una versión. |
| `PATCH` | `/locations/{id}/coordinates` | `warehouse.map.manage` | Actualiza coordenadas dentro del lienzo. |
| `GET` | `/locations/{id}/qr` | `warehouse.location.view` | Token opaco y URLs de etiqueta/consulta. |
| `GET` | `/locations/{id}/qr.svg` | `warehouse.location.view` | SVG real generado en backend. |
| `GET` | `/locations/lookup?qr_token=…` | `warehouse.location.view` | Resuelve un token opaco con alcance por almacén. |

### Controles

- **UB-010:** los nodos del mapa se derivan de `WmsCatalogService.locations()` en cada consulta.
  El plano no es fuente de verdad ni modifica saldos.
- **Fondo:** PNG/JPG/WEBP por extensión *y* cabecera mágica, máximo 5 MB, SHA-256 guardado,
  ruta confinada al directorio de adjuntos. Si falla la creación de versión o la auditoría, se elimina el archivo recién escrito.
- **Coordenadas:** `Decimal`, no `float`; se validan contra `width`/`height` de la versión activa.
- **Auditoría:** `WMS_MAP_VERSION_CREATED`, `WMS_MAP_BACKGROUND_UPLOAD` y
  `WMS_LOCATION_COORDINATES_UPDATED`, con `before`/`after` y actor.
- **QR:** token opaco sin almacén, código ni credenciales (`secrets.token_urlsafe`). SVG en
  backend con `qrcode`; la respuesta impide caché.

---

## 4. Frontend

- `LocationMap`, `LocationMapNode`, `LocationMapVersion`, `LocationQr`, `LocationLookup` y
  `LocationCoordinatesOut` en `src/api/types.ts`; métodos en `src/api/client.ts`.
- `VirtualMap.tsx`: selector de almacén, aviso referencial, rejilla y nodos posicionados por
  porcentaje, panel lateral con jerarquía/estado/ocupación, edición de coordenadas, QR opaco,
  carga de fondo, nueva versión e historial.
- Integrado en `Locations.tsx`; el nodo seleccionado sincroniza la ficha de ubicación.
- `PERM.MANAGE_MAPS` (`warehouse.map.manage` / `mapas.almacen.administrar`) controla la
  administración del plano. Sin ese permiso, los campos de coordenadas quedan deshabilitados
  y no aparecen las acciones de versión/fondo. El backend vuelve a verificar el permiso.
- Estilos en `src/styles.css`; el aviso usa ámbar para distinguirse de estados administrativos.

---

## 5. Límites

1. Plano 2D únicamente en este documento (Lote 3). La vista 3D interactiva y el inventario conectado se entregan en el Lote 6; véase `docs/RESULTADOS_LOTE6_ALMACEN_VIRTUAL.md` y la ruta `/almacen-virtual`.
2. No hay captura móvil, escaneo con cámara ni `wms.scan_event`.
3. No existen aún órdenes de movimiento (`wms.movement_order`): D-06 sigue sin aprobarse.
4. El fondo es una referencia visual; no se mide ni se valida contra el almacén físico.
5. La semilla usa coordenadas sintéticas; no se usaron planos ni datos reales.
6. No se conectó a CONTPAQi ni a Sierra Madre GMAO; no se publicaron puertos ni se hizo `push`.
