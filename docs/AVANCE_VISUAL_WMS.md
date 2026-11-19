# Avance visual del WMS · Lote A

## 1. Objetivo visual

Dotar al almacén de una interfaz clara para tres tareas concretas: encontrar materiales, entender dónde están y crear ubicaciones físicas con trazabilidad. La interfaz es de demostración: usa datos sintéticos y muestra de forma permanente que el inventario es operativo, no el oficial de CONTPAQi.

## 2. Principios aplicados

- **Cinta de demostración** en todas las pantallas WMS: `DEMOSTRACIÓN · Datos sintéticos aislados · Inventario operativo, no oficial`.
- **Etiqueta de alcance** `Lote A · WMS` en el encabezado para distinguir el avance del resto del ERP.
- **Densidad moderada:** filtros arriba, resultados a la izquierda y ficha de detalle a la derecha.
- **Cifras legibles:** cantidades formateadas con `formatNumber`; porcentajes de ocupación con barra de progreso y tono ámbar cuando supera 85 %.
- **Sin valores manuales de existencia:** la ocupación y los disponibles se derivan de saldos; la UI lo indica textualmente.
- **Permisos visibles:** las altas solo aparecen para roles con `catalog.manage` o `warehouse.location.manage`; el servidor vuelve a validar.

## 3. Pantallas entregadas

### 3.1 Catálogo de materiales · `/catalogo`

- Buscador con texto libre, familia, almacén, ubicación física, equipo GMAO y opción `Solo activos`.
- Lista de resultados con código, descripción, familia, indicadores de lote/serie/consumible y existencias.
- Ficha de material con:
  - fotografía o placeholders `Sin fotografía registrada`;
  - existencia, reservado y disponible;
  - datos técnicos: fabricante, parte, código de barras, costo, reorder, safety stock, máximo, peso y volumen;
  - cargas de fotografía JPG/PNG/WEBP ≤ 2 MB para usuarios con permiso;
  - tabla de ubicaciones con lote, zona, existencia y disponible;
  - chips de lotes, series, proveedores y referencias cruzadas;
  - últimos movimientos con documento, dirección, cantidad, saldo y timestamp;
  - documentos relacionados.
- Alta de familias con código y nombre, registrada en auditoría.

### 3.2 Ubicaciones · `/ubicaciones`

- Filtros por texto, almacén, tipo de ubicación y estado.
- Tabla con código, jerarquía `zona · pasillo · estante`, almacén, tipo, estado, ocupación y número de artículos.
- Formulario de alta con almacén, código, zona, pasillo, estante, nivel, posición, tipo, capacidad, estado, surtido y recepción.
- Ficha de ubicación con capacidad, ocupación, restricciones, saldos por lote y token de etiqueta.
- El token se muestra como texto legible `WMS:<almacén>:<código>`; se indica explícitamente que el QR gráfico está pendiente.

## 4. Cambios de implementación

- `frontend/src/features/catalog/Catalog.tsx`: pantalla de catálogo y ficha.
- `frontend/src/features/wms/Locations.tsx`: pantalla de ubicaciones y ficha.
- `frontend/src/api/types.ts` y `client.ts`: contratos y métodos WMS.
- `frontend/src/auth/permissions.ts`: `VIEW_CATALOG`, `MANAGE_CATALOG`, `VIEW_LOCATIONS`, `MANAGE_LOCATIONS`.
- `frontend/src/components/Layout.tsx`: nuevo grupo de menú `WMS · Catálogo`.
- `frontend/src/components/ui.tsx`: icono `search` disponible en paneles.
- `frontend/src/styles.css`: `detail-stack`, `detail-header`, `link-button` y ajustes de ficha.
- Pruebas: `Catalog.test.tsx` y `Locations.test.tsx` cubren búsqueda, ficha, altas y ocultamiento de acciones sin permiso.

## 5. Evidencias visuales reales

Se capturó el texto renderizado por Chromium desde las rutas autenticadas:

- `docs/evidencias_demo/01_catalogo_ficha_material.txt`
- `docs/evidencias_demo/02_ubicaciones_ficha.txt`

Ambos archivos incluyen URL, sesión (`demo.admin`) y el contenido real del elemento `<main>`. No se generaron capturas de pantalla porque la ventana de escritorio no estaba visible durante la misión; no se sustituyeron por maquetas ni imágenes inventadas.

## 6. Pendiente visual

1. Generación y lectura de QR gráfico para las etiquetas de ubicación.
2. Vista de herramientas y series con estado operativo.
3. Revisión responsive en tablet industrial y modo oscuro completo.
4. Auditoría de accesibilidad con Lighthouse sobre las dos rutas nuevas.
5. Flujo de movimientos/transferencias con selección visual de ubicación origen y destino.

## 7. Resultado verificado

- `npm.cmd run build`: correcto.
- `npm.cmd run test -- --run`: 14/14.
- `python scripts\verificar_portal.py`: 22/22, incluye cuatro comprobaciones WMS en vivo.
- Menú WMS confirmado en el navegador con el bundle `index-QWrB8VnM.js`; se descartó una falsa lectura causada por caché del bundle anterior.
