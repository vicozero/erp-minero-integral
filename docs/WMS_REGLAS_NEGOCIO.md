# WMS avanzado — Reglas de negocio e integridad

**Fecha:** 2026-11-18

**Estado:** DISEÑO normativo. No se implementó código en este entregable.
**Autoridad:** `AGENTS.md`, Fase 4 y documentos de arquitectura/datos WMS.

---

## 1. Principios superiores

| ID | Principio |
|---|---|
| P-01 | CONTPAQi sigue siendo el inventario y la contabilidad oficiales. |
| P-02 | El ERP mantiene un espejo operativo; no crea un segundo inventario oficial. |
| P-03 | Todo efecto físico nace de un documento con folio único. |
| P-04 | Todo movimiento es inmutable; las correcciones son contrapartidas o reversiones. |
| P-05 | Toda operación sensible es atómica: negocio + auditoría + outbox en una transacción. |
| P-06 | Toda operación repetible usa idempotencia. |
| P-07 | La IA propone; el humano autoriza. |
| P-08 | El backend es la autoridad de RBAC y alcance. |
| P-09 | Los datos de prueba son sintéticos. |
| P-10 | Ninguna regla nueva autoriza saltarse un workflow aprobado. |

---

## 2. Reglas transversales

| ID | Regla | Estado |
|---|---|---|
| RN-001 | Todo documento usa `next_document_number()`: `TIPO-SERIE-AÑO-NNNNNN`. | Implementado |
| RN-002 | El número de serie se asigna con `FOR UPDATE` sobre `doc.document_numbering`. | Implementado |
| RN-003 | Toda escritura sensible valida `idempotency_key` antes de producir efectos. | Implementado parcial |
| RN-004 | Una clave de idempotencia reutilizada con otra operación se rechaza con 409. | Implementado |
| RN-005 | Los saldos se leen y bloquean en orden determinista por almacén, artículo, lote y ubicación. | Parcial: falta ubicación/lote real |
| RN-006 | `available_qty = on_hand_qty - reserved_qty`; nunca se almacena como columna manual. | Implementado |
| RN-007 | `on_hand_qty >= 0`, `reserved_qty >= 0` y `on_hand_qty >= reserved_qty`. | Implementado en CHECK |
| RN-008 | No se permite sobreentrega ni sobrereserva. | Implementado para requisiciones |
| RN-009 | Material en tránsito se registra separadamente del disponible. | Pendiente Lote C |
| RN-010 | Toda reversión referencia el movimiento original y lleva motivo. | Metadato existe; servicio pendiente |
| RN-011 | Ninguna operación elimina movimientos, asientos, eventos ni documentos. | Implementado por convención + trigger en auditoría |
| RN-012 | Actor, autorizador, timestamp, `request_id` y correlación quedan registrados. | Implementado |
| RN-013 | Solo se reintentan deadlocks/serialización; nunca violaciones de regla de negocio. | Pendiente de forma explícita |
| RN-014 | Los listados deben exigir filtros de alcance y paginación. | Pendiente |
| RN-015 | Todo permiso nuevo se define en backend con alias español/inglés. | Parcial |

---

## 3. A. Catálogo maestro

| ID | Regla |
|---|---|
| CA-001 | El código de artículo es único por compañía; no se reutiliza tras dar de baja. |
| CA-002 | Un artículo debe tener UOM base y, si aplica, UOM de compra y conversiones válidas. |
| CA-003 | Todo factor de conversión es > 0 y tiene vigencia controlada. |
| CA-004 | Las equivalencias sólo se usan si `authorised=true` y existe aprobador. |
| CA-005 | Una equivalencia no sustituye silenciosamente el artículo solicitado. |
| CA-006 | `lot_tracked=true` exige lote real en entradas, salidas y traspasos. |
| CA-007 | `serial_tracked=true` exige serie real y única por artículo. |
| CA-008 | Fotografías y adjuntos se almacenan fuera de BD con SHA-256 y ruta controlada. |
| CA-009 | Equipos compatibles se registran como relación explícita, no como texto libre. |
| CA-010 | Costos de referencia son informativos hasta que Finanzas apruebe la política de valuación. |
| CA-011 | Materiales consumibles, retornables y herramientas se distinguen por atributos, no por código secreto. |
| CA-012 | La baja de un maestro es lógica (`is_active=false`), nunca física. |

---

## 4. B. Ubicaciones

| ID | Regla |
|---|---|
| UB-001 | Toda ubicación pertenece a un almacén existente. |
| UB-002 | El código de ubicación es único dentro del almacén. |
| UB-003 | La jerarquíaStorage Location sigue almacén → zona → pasillo → anaquel → nivel → posición. |
| UB-004 | Las ubicaciones de recepción, cuarentena, despacho, tránsito y scraps se identifican por tipo. |
| UB-005 | Ninguna operación supera la capacidad disponible de la ubicación, salvo autorización explícita. |
| UB-006 | Las restricciones por familia, temperatura o mezcla de lotes/series se validan antes de sugerir la ubicación. |
| UB-007 | El token QR es único, opaco y no contiene credenciales. |
| UB-008 | Una ubicación `BLOCKED` o `INACTIVE` no acepta movimientos. |
| UB-009 | La sugerencia de ubicación es determinista y explicable; no obliga al operario. |
| UB-010 | El plano 2D es una proyección de `mdm.storage_location`, no una fuente de verdad. |

---

## 5. C. Entradas

| ID | Regla |
|---|---|
| EN-001 | Toda entrada se ampara en OC, devolución, traspaso o entrada extraordinaria autorizada. |
| EN-002 | Las recepciones parciales acumulan `received_qty` sin exceder lo permitido. |
| EN-003 | `received_qty <= ordered_qty - cancelled_qty + tolerancia autorizada`. |
| EN-004 | La verificación contra documento compara artículo, cantidad, UOM, proveedor y almacén. |
| EN-005 | Lote, serie, caducidad y evidencia se capturan antes de publicar el movimiento. |
| EN-006 | Material en cuarentena no está disponible para surtido. |
| EN-007 | Una entrada genera `RECEIPT`/`RETURN` en `inv.stock_movement` y actualiza el saldo con bloqueo. |
| EN-008 | Las diferencias se registran; no se corrigen sobrescribiendo la recepción. |
| EN-009 | Entrada extraordinaria requiere motivo y aprobación de rol autorizado. |
| EN-010 | Toda entrada genera auditoría, evento de documento y outbox en la misma transacción. |

---

## 6. D. Salidas

| ID | Regla |
|---|---|
| SA-001 | Las salidas por requisición requieren línea autorizada y reserva activa. |
| SA-002 | Las salidas por OT, equipo o departamento requieren documento de consumo y autorización. |
| SA-003 | No se entrega más de lo autorizado menos lo ya entregado/cancelado. |
| SA-004 | Al entregar se consume la reserva y se descuentan `on_hand_qty` y `reserved_qty`. |
| SA-005 | Se registran quién entrega y quién recibe, con timestamp. |
| SA-006 | El costo del consumo se imputa en la misma transacción del movimiento cuando la política esté aprobada. |
| SA-007 | Las devoluciones se documentan como entradas con motivo y referencia a la salida original. |
| SA-008 | Las cancelaciones liberan reservas y dejan rastro documental; nunca borran la salida. |
| SA-009 | Una salida parcial no cierra la línea; el cierre requiere todas las líneas entregadas/canceladas. |
| SA-010 | Las reversiones de salida se crean como movimientos opuestos con `reversal_of_id`. |

---

## 7. E. Traspasos

| ID | Regla |
|---|---|
| TR-001 | Todo traspaso tiene origen, destino, artículo, lote/serie y cantidad. |
| TR-002 | Se distinguen solicitud, autorización, preparación, despacho, tránsito y recepción. |
| TR-003 | El despacho genera `TRANSFER_OUT` y la recepción genera `TRANSFER_IN`, unidos por `transfer_id`. |
| TR-004 | El saldo en tránsito no suma al disponible del almacén destino. |
| TR-005 | La recepción puede ser parcial y acumular diferencias. |
| TR-006 | Las diferencias requieren motivo, evidencia y autorización. |
| TR-007 | El orden de bloqueo es determinista para evitar deadlocks entre almacenes. |
| TR-008 | Traspasos entre unidades mineras requieren aprobación ampliada y control de propiedad. |
| TR-009 | La trazabilidad permite reconstruir quién solicitó, autorizó, preparó, despachó y recibió. |
| TR-010 | Un traspaso cancelado revierte sólo lo no recibido y documenta el remanente. |

---

## 8. F. Inventarios físicos

| ID | Regla |
|---|---|
| IC-001 | Existen conteos generales, cíclicos ABC, por zona y ciegos. |
| IC-002 | El conteo ciego oculta la cantidad sistema al contador. |
| IC-003 | Las sesiones pueden bloquear movimientos en su alcance. |
| IC-004 | El reconteo se registra como una nueva línea de conteo, no sobrescribe el primero. |
| IC-005 | Las diferencias requieren clasificación, motivo y autorizador. |
| IC-006 | Sólo una diferencia autorizada genera `ADJUSTMENT_IN/OUT`. |
| IC-007 | El ajuste genera kardex con documento, motivo y actor. |
| IC-008 | La conciliación compara existencias por almacén, ubicación, lote, serie y costo. |
| IC-009 | Un conteo no modifica el sistema oficial; CONTPAQi requiere su propio proceso. |
| IC-010 | Los snapshots son inmutables por sesión. |

---

## 9. G. Herramientas

| ID | Regla |
|---|---|
| HE-001 | Toda herramienta retornable tiene responsable mientras está prestada. |
| HE-002 | El préstamo puede ser individual o por cuadrilla con responsable designado. |
| HE-003 | La devolución puede ser parcial y actualiza el resguardo. |
| HE-004 | Estado físico, mantenimiento, calibración y vencimiento se registran por herramienta. |
| HE-005 | Herramienta extraviada o dañada genera evento, responsable y decisión de cargo o baja. |
| HE-006 | El historial de responsables es append-only. |
| HE-007 | Un préstamo vencido dispara alerta; no crea movimientos automáticos. |
| HE-008 | Si la herramienta se trata como artículo de inventario, el préstamo usa reserva/entrega normal. |

---

## 10. H. Costos

| ID | Regla |
|---|---|
| CO-001 | Sólo se aplica el método de valuación aprobado por Finanzas. |
| CO-002 | Costo promedio y FIFO son opciones; ninguna se activa por defecto sin decisión. |
| CO-003 | Todo consumo genera asiento valorizado en la misma transacción del movimiento. |
| CO-004 | El asiento referencia movimiento, documento, objeto de costo y capas consumidas. |
| CO-005 | Costos se imputan por equipo, OT, departamento, centro de costo y ubicación minera cuando aplique. |
| CO-006 | Las reversiones son asientos nuevos con referencia al original. |
| CO-007 | El kardex valorizado es una proyección; no se reescriben costos históricos. |
| CO-008 | Inventario obsoleto e inmovilizado se calcula por antigüedad y sin movimiento. |
| CO-009 | La conciliación con CONTPAQi es informativa hasta aprobación formal. |
| CO-010 | El ERP no calcula impuestos fiscales oficiales en esta etapa. |

---

## 11. I. Reabastecimiento

| ID | Regla |
|---|---|
| RE-001 | Todo artículo crítico tiene línea base de consumo, lead time y stock de seguridad. |
| RE-002 | Punto de reorden = consumo medio durante lead time + stock de seguridad. |
| RE-003 | Stock mínimo y máximo se respetan en las sugerencias. |
| RE-004 | Las sugerencias usan consumo histórico de movimientos posteados. |
| RE-005 | Una sugerencia no genera OC automática sin aprobación. |
| RE-006 | Las alertas de desabasto incluyen artículo, almacén, criticidad y días estimados. |
| RE-007 | Si no hay historial suficiente, se reporta “datos insuficientes” en vez de inventar un pronóstico. |
| RE-008 | Los materiales críticos se priorizan sobre rotación normal. |

---

## 12. J. Captura móvil

| ID | Regla |
|---|---|
| MO-001 | Todo dispositivo queda asociado a usuario, almacenes permitidos y sesión vigente. |
| MO-002 | El escaneo de QR/código valida permisos antes de mostrar datos sensibles. |
| MO-003 | Recepción, salida, traspaso y conteo usan los mismos servicios que la UI web. |
| MO-004 | La evidencia fotográfica queda ligada al documento y al `request_id`. |
| MO-005 | Cada intento móvil lleva idempotencia; el reintento no duplica movimientos. |
| MO-006 | El dispositivo nunca será fuente oficial de existencias. |
| MO-007 | Sin conexión, se permite captura controlada sólo si se diseñó cola idempotente aprobada. |
| MO-008 | La sesión se cierra por inactividad y no almacena tokens en `localStorage`. |

---

## 13. K. Analítica

| ID | Regla |
|---|---|
| AN-001 | Exactitud = coincidencias entre conteo y sistema / líneas contadas. |
| AN-002 | Rotación = consumo periodo / stock promedio. |
| AN-003 | Cobertura = stock disponible / consumo medio diario. |
| AN-004 | Cumplimiento de surtido = líneas entregadas completas / líneas autorizadas. |
| AN-005 | Material sin movimiento se identifica por periodo configurable. |
| AN-006 | Consumo por equipo y área se deriva de movimientos con objeto de costo. |
| AN-007 | Diferencias y traspasos pendientes se muestran con responsable y antigüedad. |
| AN-008 | Costos valorizados se derivan de asientos/capas, no de estimaciones de UI. |
| AN-009 | Exportación PDF/Excel usa datos autorizados y sin secretos. |
| AN-010 | Los KPIs se calculan desde proyecciones de solo lectura. |

---

## 14. L. Inteligencia artificial

| ID | Regla |
|---|---|
| IA-001 | La IA no crea, modifica ni autoriza movimientos, reservas ni asientos. |
| IA-002 | Toda recomendación incluye confianza, motivo, datos de soporte y versión del modelo/regla. |
| IA-003 | Toda recomendación requiere revisión humana antes de convertirse en documento. |
| IA-004 | Búsqueda semántica nunca decide sustitución de artículo; sólo propone candidatos. |
| IA-005 | Duplicados se entregan como candidatos con puntaje y evidencia. |
| IA-006 | Pronósticos requieren volumen mínimo de datos; si no hay, se abstiene. |
| IA-007 | Anomalías se clasifican y revisan; no bloquean operaciones automáticamente salvo regla aprobada. |
| IA-008 | Sugerencia de ubicación respeta capacidad y restricciones antes de proponer. |
| IA-009 | Priorización de tareas es informativa para el operario. |
| IA-010 | Entrenamiento y demostración usan exclusivamente datos sintéticos o autorizados. |
| IA-011 | Se registra la disposición humana: aceptada, rechazada o ignorada, con motivo. |

---

## 15. Integridad y conciliación

| ID | Regla |
|---|---|
| IN-001 | Conciliación por lote, serie, ubicación, documento y costo. |
| IN-002 | `stock_balance` y `stock_reservation` no pueden divergir sin explicación documentada. |
| IN-003 | Toda cancelación conserva el documento original y su motivo. |
| IN-004 | Toda operación reversible define qué se revierte, quién autoriza y qué evento se emite. |
| IN-005 | No se permite `DELETE` físico en tablas de negocio. |
| IN-006 | Los IDs externos se almacenan como referencia, nunca como llave primaria interna. |
| IN-007 | Duplicados de importación se detectan por hash + clave externa + mapeo. |
| IN-008 | Los reintentos usan backoff acotado y dead-letter; nunca reintentan errores de validación. |
| IN-009 | Las diferencias de conciliación no ajustan CONTPAQi automáticamente. |
| IN-010 | La bitácora cubre toda acción sensible nueva. |

---

## 16. Matriz de estado

| Estado | Significado |
|---|---|
| Implementado | Existe en código y pruebas |
| Parcial | Existe parte de la regla o sólo metadato |
| Pendiente | Requiere lote posterior |
| Decisión | Depende de aprobación de negocio |

| Regla | Estado |
|---|---|
| RN-001 a RN-008 | Implementado/Parcial |
| RN-009 a RN-015 | Pendiente |
| CA-001 a CA-012 | Pendiente salvo unicidad básica |
| UB-001 a UB-010 | Pendiente |
| EN-001 a EN-010 | Parcial/Pendiente |
| SA-001 a SA-010 | Parcial/Pendiente |
| TR-001 a TR-010 | Pendiente |
| IC-001 a IC-010 | Pendiente |
| HE-001 a HE-008 | Pendiente |
| CO-001 a CO-010 | Parcial/Pendiente |
| RE-001 a RE-008 | Pendiente |
| MO-001 a MO-008 | Pendiente |
| AN-001 a AN-010 | Pendiente |
| IA-001 a IA-011 | Pendiente |
| IN-001 a IN-010 | Parcial/Pendiente |

---

## 17. Criterios de verificación

Cada regla nueva debe acompañarse de:

1. Restricción en base cuando sea posible (CHECK/UNIQUE/FK).
2. Validación en servicio con mensaje de error accionable en español.
3. Prueba automatizada positiva y negativa.
4. Registro de auditoría.
5. Evento outbox si impacta integración.
6. Documentación de reversión o cancelación.
7. Prueba de concurrencia cuando toque saldos.
