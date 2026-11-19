# Resultados — Módulo documental (Lote 1, parcial)

Fecha: 19/11/2026. Estado: **formatos implementados, probados localmente y aprobados visualmente por el usuario**. El Lote 1 completó la fase de PDF/XLSX; el semáforo SLA quedó implementado en el Lote 2 (`docs/RESULTADOS_SEMAFORO_SLA.md`) y el almacén virtual quedó cubierto en lotes posteriores.

> **Actualización Lote 5:** la captura nominal de firmas, el proveedor recomendado y la validación final en portal están documentados en `docs/RESULTADOS_LOTE5_DOCUMENTOS.md` y `docs/VALIDACION_FORMATOS_PDF_EXCEL.md`.

## Decisiones registradas

| Tema | Decisión |
|---|---|
| Plantilla VA | `VA-000162.pdf`, confirmada por el usuario; diseño idéntico al 165 |
| Folio VA | Serie `VA / LAG`, sin año, `VA-000166` en adelante |
| Plantilla REQ | Versión Carta/Nitro del escritorio, no la copia A4/Excel |
| Imágenes del almacén | Los 4 PNG se registrarán como fondos disponibles; no se presentarán como plano exacto (fase posterior) |
| SLA | Configuración aprobada e implementada en el Lote 2; emergencia desactivada hasta aprobación explícita |

## Cambios entregados

- Dependencias: `reportlab>=4.2` y `openpyxl>=3.1` en `backend/pyproject.toml`.
- Numeración: `next_document_number()` acepta `year`, `start_number` y `number_format` sin alterar el generador estándar.
- Permisos: `document.render`, `warehouse.voucher.create`, `warehouse.voucher.issue`; rol `ADMIN` y roles operativos/lectura actualizados; tipo documental `VA`.
- Modelos nuevos en `doc`: `document_template`, `document_render`, `warehouse_voucher`, `warehouse_voucher_line`.
- Migración aditiva `c1d2e3f4a5b6` (depende de `b7c8d9e0f1a3`). No elimina ni reescribe datos; `downgrade()` falla deliberadamente.
- Renderizadores: `render_va.py` (10 partidas/hoja) y `render_req.py` (21 partidas/hoja), con plantillas versionadas en `templates.py` y logotipos extraídos a `assets/`.
- Servicio: creación/emisión de vales, render, reimpresión de versión emitida, auditoría, eventos de documento e idempotencia.
- Router: `/api/v1/documents/...`, registrado en `app.main`.
- Pruebas: `tests/test_documentation.py` (12 pruebas) y ajustes en dos pruebas de esquema/migración para aceptar la nueva revisión.
- Evidencias: `docs/EVIDENCIA_FORMATOS/` y script reproducible `backend/scripts/generar_evidencia_formatos.py`.
- Documentación: `docs/VALES_ALMACEN_FORMATOS.md` y `docs/REQUISICIONES_FORMATOS.md`.

## Verificación ejecutada

```powershell
cd E:\ERP_MINERO\backend
python -m ruff check app/modules/documentation app/api/v1/routers/documentation.py tests/test_documentation.py
python -m mypy app/modules/documentation app/api/v1/routers/documentation.py tests/test_documentation.py --follow-imports=silent
python -m pytest -q
python scripts/generar_evidencia_formatos.py
```

Resultados:

- `ruff`: sin errores.
- `mypy`: sin errores en los archivos nuevos.
- `pytest`: **100 pruebas aprobadas** sobre PostgreSQL `erp_minero_test`, sin SQLite.
- Alembic: `c1d2e3f4a5b6 (head)` verificado en `erp_minero_test`.
- Evidencias generadas con datos sintéticos; ninguna ruta local se expone en la API.

## Cadena de custodia

- PDF/XLSX: `sha256` por render, inmutable; reimpresión apunta al render original.
- Auditoría: `VOUCHER_CREATE`, `VOUCHER_ISSUE`, `DOCUMENT_RENDER`, `DOCUMENT_REPRINT`, con actor, entidad y hash.
- Documentos: eventos `DOCUMENT_NUMBER_ISSUED`, `VOUCHER_CREATED`, `VOUCHER_ISSUED`, `VOUCHER_RENDERED`, `VOUCHER_REPRINTED`, `REQUISITION_RENDERED`, `REQUISITION_REPRINTED`.
- Descargar no altera stock, reservas ni autorizaciones; se comprueba en pruebas contando el kardex antes y después.

## Limitaciones conocidas

1. **Revisión visual resuelta**: el usuario aprobó los PDF/XLSX/PNG de `docs/EVIDENCIA_FORMATOS/` el 19/11/2026. La comparación automatizada sigue siendo estructural, no una sustitución de esa revisión humana.
2. El XLSX del REQ usa columnas de meses simplificadas respecto del original; conserva área de impresión y edición, pero no es una réplica celda por celda.
3. No se capturan firmas gráficas; la aprobación electrónica se distingue por texto y por el historial de aprobación.
4. `PROVEEDOR RECOMENDADO` y `PROGRAMADO` se imprimen vacíos por falta de fuente autorizada.
5. Las imágenes PNG del almacén están copiadas en `docs/plantillas_referencia/` y en la raíz del repositorio; la raíz contiene también los PDF originales copiados por el usuario. **No se borraron ni movieron**: requiere decisión antes de limpiar.
6. No se declaró apto para producción; no hubo push, ni contacto con CONTPAQi/GMAO, ni exposición de red.

## Siguiente paso

Tras la revisión visual de estos formatos: implementar el **semáforo de requisiciones** (configuración por prioridad/departamento/tipo, cálculo en backend, historial y filtros), y después el **almacén virtual** (catálogo jerárquico, plano 2D, panel lateral y permisos), para cerrar con la regresión integral.
