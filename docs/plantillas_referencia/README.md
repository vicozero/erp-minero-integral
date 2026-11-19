# Plantillas visuales de referencia

Esta carpeta contiene las **copias exactas** de los PDF autorizados por el usuario, sin editarlos ni renombrarlos:

1. `VA-000162.pdf` — SHA-256 `82c868df58f06ed7df029c8a67e8239b6f73df92e95f0c8bae8b04cc8a5f6e2e`.
2. `Requisicion_REQ-0006_JL-03_2026-11-13.pdf` — SHA-256 `5df7f95ee6d850f2b067708a40ad6ea4551c47a7dd2578a3519bde4800526062` (versión Carta/Nitro del escritorio).

## Estado actual

Ambas copias están versionadas en Git. El usuario confirmó la selección el 19/11/2026:

- El vale autorizado es `VA-000162.pdf`. Durante la Fase 0 se inspeccionó `VA-000165.pdf`, estructuralmente idéntico; por decisión del usuario no se reproduce el folio 165 y la numeración nueva comienza en `VA-000166`.
- Para la requisición se eligió la versión Carta/Nitro, no la copia A4/Excel que también circuló fuera del repositorio.

Además de los PDF se versionan los cuatro PNG disponibles como posibles fondos del almacén virtual. **No se presentan como plano exacto**; su uso se decidirá en la fase del almacén virtual.

## Inspección

El análisis técnico de geometría, capa de texto y trazos está en `INSPECCION_PLANTILLAS.md`. Las evidencias comparativas de los formatos generados están en `docs/EVIDENCIA_FORMATOS/`.

## Regla de integridad

- No reconstruir los originales a partir de sus nombres.
- No inventar firmas, aprobaciones ni datos de encabezado.
- No tratar estas copias como datos sintéticos.
- No publicar los PDF en el portal ni incluirlos en respuestas de API.
- Toda corrección de formato se valida contra el SHA-256 indicado arriba.
