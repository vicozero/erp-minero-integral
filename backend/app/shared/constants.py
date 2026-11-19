"""Catálogo de permisos y roles.

Se conservan los códigos de la Fase 2 (ingleses) para no romper contratos
existentes y se agregan los códigos en español solicitados para Fase 3.
Todos se comprueban en backend; el frontend solo los usa para construir menús.
"""

from __future__ import annotations

PERMISSIONS_LEGACY: tuple[str, ...] = (
    "admin.users.manage",
    "audit.view",
    "inventory.availability.view",
    "inventory.issue",
    "inventory.kardex.view",
    "inventory.reserve",
    "purchase.order.approve",
    "purchase.order.create",
    "purchase.receive",
    "purchase.view",
    "requisition.approve",
    "requisition.cancel",
    "requisition.create",
    "requisition.history.view",
    "requisition.submit",
    "requisition.view",
)

PERMISSIONS_FASE3: tuple[str, ...] = (
    "requisiciones.crear",
    "requisiciones.ver_propias",
    "requisiciones.ver_departamento",
    "requisiciones.autorizar",
    "requisiciones.cancelar",
    "requisiciones.historial",
    "almacenes.consultar",
    "almacenes.reservar",
    "almacenes.surtir",
    "almacenes.kardex",
    "compras.consultar",
    "compras.crear",
    "compras.autorizar",
    "compras.recibir",
    "usuarios.administrar",
    "usuarios.consultar",
    "roles.asignar",
    "departamentos.consultar",
    "sesiones.consultar",
    "auditoria.consultar",
)

# Códigos canónicos internos a los que apuntan los alias en español.
PERMISSIONS_INTERNAL: tuple[str, ...] = (
    "requisition.view_own",
    "requisition.view_department",
    "user.view",
    "role.assign",
    "department.view",
    "session.view",
)

# Lote A del WMS: lectura de catálogo/ubicaciones y altas controladas.
PERMISSIONS_WMS: tuple[str, ...] = (
    "catalog.view",
    "catalog.manage",
    "warehouse.location.view",
    "warehouse.location.manage",
)

# Lote B del WMS: contratos de movimientos. B.0 solo registra los códigos;
# no hay endpoints ni reglas de negocio que dependan de decisiones pendientes.
PERMISSIONS_WMS_LOTE_B_CREATE: tuple[str, ...] = (
    "wms.receipt.create",
    "wms.issue.create",
    "wms.return.create",
    "wms.reversal.create",
)
PERMISSIONS_WMS_LOTE_B_APPROVE: tuple[str, ...] = (
    "wms.receipt.approve",
    "wms.issue.approve",
    "wms.return.approve",
    "wms.reversal.approve",
)
PERMISSIONS_WMS_LOTE_B_VIEW: tuple[str, ...] = (
    "wms.kardex.view",
    "warehouse.stock.view",
)
PERMISSIONS_WMS_LOTE_B: tuple[str, ...] = (
    PERMISSIONS_WMS_LOTE_B_CREATE
    + PERMISSIONS_WMS_LOTE_B_APPROVE
    + PERMISSIONS_WMS_LOTE_B_VIEW
)

# Aliases en español de los permisos operativos del Lote B. Se conserva
# `almacenes.kardex -> inventory.kardex.view` para no romper el contrato actual.
PERMISSIONS_WMS_LOTE_B_ALIASES: tuple[str, ...] = (
    "almacenes.entradas",
    "almacenes.salidas",
    "almacenes.devoluciones",
    "almacenes.reversos",
    "entradas.crear",
    "salidas.crear",
    "devoluciones.crear",
    "reversos.crear",
)

PERMISSIONS: tuple[str, ...] = (
    PERMISSIONS_LEGACY
    + PERMISSIONS_FASE3
    + PERMISSIONS_INTERNAL
    + PERMISSIONS_WMS
    + PERMISSIONS_WMS_LOTE_B
    + PERMISSIONS_WMS_LOTE_B_ALIASES
)

# Alias español -> código canónico heredado. Permite que una política escrita
# con un código u otro se resuelva a la misma comprobación.
PERMISSION_ALIASES: dict[str, str] = {
    "requisiciones.crear": "requisition.create",
    "requisiciones.autorizar": "requisition.approve",
    "requisiciones.cancelar": "requisition.cancel",
    "requisiciones.historial": "requisition.history.view",
    "almacenes.consultar": "inventory.availability.view",
    "almacenes.reservar": "inventory.reserve",
    "almacenes.surtir": "inventory.issue",
    "almacenes.kardex": "inventory.kardex.view",
    "compras.consultar": "purchase.view",
    "compras.crear": "purchase.order.create",
    "compras.autorizar": "purchase.order.approve",
    "compras.recibir": "purchase.receive",
    "usuarios.administrar": "admin.users.manage",
    "auditoria.consultar": "audit.view",
    "requisiciones.ver_propias": "requisition.view_own",
    "requisiciones.ver_departamento": "requisition.view_department",
    "usuarios.consultar": "user.view",
    "roles.asignar": "role.assign",
    "departamentos.consultar": "department.view",
    "sesiones.consultar": "session.view",
    "catalogo.consultar": "catalog.view",
    "catalogo.administrar": "catalog.manage",
    "ubicaciones.consultar": "warehouse.location.view",
    "ubicaciones.administrar": "warehouse.location.manage",
    "almacenes.entradas": "wms.receipt.create",
    "almacenes.salidas": "wms.issue.create",
    "almacenes.devoluciones": "wms.return.create",
    "almacenes.reversos": "wms.reversal.create",
    "entradas.crear": "wms.receipt.create",
    "salidas.crear": "wms.issue.create",
    "devoluciones.crear": "wms.return.create",
    "reversos.crear": "wms.reversal.create",
}


def canonical_permission(code: str) -> str:
    return PERMISSION_ALIASES.get(code, code)


_SOLICITANTE = (
    "requisition.create",
    "requisition.submit",
    "requisition.view",
    "requisition.view_own",
    "requisition.history.view",
    "inventory.availability.view",
    "requisiciones.crear",
    "requisiciones.ver_propias",
    "requisiciones.historial",
    "almacenes.consultar",
)
_APROBADOR = (
    "requisition.approve",
    "requisition.cancel",
    "requisition.view",
    "requisition.view_department",
    "requisition.history.view",
    "inventory.availability.view",
    "requisiciones.autorizar",
    "requisiciones.cancelar",
    "requisiciones.ver_departamento",
    "requisiciones.historial",
    "almacenes.consultar",
)
_ALMACEN = (
    "inventory.availability.view",
    "inventory.reserve",
    "inventory.issue",
    "inventory.kardex.view",
    "requisition.view",
    "requisition.view_department",
    "requisition.history.view",
    "purchase.view",
    "almacenes.consultar",
    "almacenes.reservar",
    "almacenes.surtir",
    "almacenes.kardex",
    "requisiciones.ver_departamento",
    "compras.consultar",
)
_COMPRAS = (
    "purchase.order.create",
    "purchase.order.approve",
    "purchase.receive",
    "purchase.view",
    "inventory.availability.view",
    "requisition.view",
    "requisition.history.view",
    "compras.crear",
    "compras.autorizar",
    "compras.recibir",
    "compras.consultar",
    "almacenes.consultar",
)
_LECTURA = (
    "requisition.view",
    "requisition.view_department",
    "requisition.history.view",
    "inventory.availability.view",
    "inventory.kardex.view",
    "purchase.view",
    "requisiciones.ver_departamento",
    "requisiciones.historial",
    "almacenes.consultar",
    "almacenes.kardex",
    "compras.consultar",
    "departamentos.consultar",
)

_WMS_READ = ("catalog.view", "warehouse.location.view")
_WMS_MANAGE = ("catalog.manage", "warehouse.location.manage")

# Lote B: creación y consulta para almacén; aprobación para el aprobador;
# gerencia y auditoría solo lectura. ADMIN ya recibe `PERMISSIONS` completo.
_WMS_B_CREATE = PERMISSIONS_WMS_LOTE_B_CREATE + PERMISSIONS_WMS_LOTE_B_ALIASES
_WMS_B_APPROVE = PERMISSIONS_WMS_LOTE_B_APPROVE
_WMS_B_VIEW = PERMISSIONS_WMS_LOTE_B_VIEW

ROLE_PERMISSIONS: dict[str, tuple[str, ...]] = {
    "ADMIN": PERMISSIONS,
    "SOLICITANTE": _SOLICITANTE + _WMS_READ,
    "JEFE_DEPARTAMENTO": _SOLICITANTE + _APROBADOR + ("departamentos.consultar",) + _WMS_READ,
    "APROBADOR": _APROBADOR + _WMS_READ + _WMS_B_APPROVE + _WMS_B_VIEW,
    "ALMACENISTA": _ALMACEN + _WMS_READ + _WMS_MANAGE + _WMS_B_CREATE + _WMS_B_VIEW,
    "ALMACEN": _ALMACEN + _WMS_READ + _WMS_MANAGE + _WMS_B_CREATE + _WMS_B_VIEW,
    "COMPRADOR": _COMPRAS + _WMS_READ,
    "COMPRAS": _COMPRAS + _WMS_READ,
    "GERENCIA": (
        _LECTURA
        + ("audit.view", "auditoria.consultar", "sesiones.consultar")
        + _WMS_READ
        + _WMS_B_VIEW
    ),
    "AUDITOR": (
        _LECTURA
        + ("audit.view", "auditoria.consultar", "usuarios.consultar")
        + _WMS_READ
        + _WMS_B_VIEW
    ),
}

ROLE_LABELS: dict[str, str] = {
    "ADMIN": "Administrador",
    "SOLICITANTE": "Solicitante",
    "JEFE_DEPARTAMENTO": "Jefe de departamento",
    "APROBADOR": "Aprobador (compatible)",
    "ALMACENISTA": "Almacén (compatible)",
    "ALMACEN": "Almacén",
    "COMPRADOR": "Compras (compatible)",
    "COMPRAS": "Compras",
    "GERENCIA": "Gerencia",
    "AUDITOR": "Auditor",
}

ADMIN_ROLE_CODES: frozenset[str] = frozenset({"ADMIN"})
APPROVER_ROLE_CODES: frozenset[str] = frozenset({"ADMIN", "APROBADOR", "JEFE_DEPARTAMENTO"})

REQUISITION_STATUSES = ("DRAFT", "SUBMITTED", "APPROVED", "PARTIALLY_APPROVED", "REJECTED", "CANCELLED", "IN_PROGRESS", "CLOSED")
REQUISITION_LINE_STATUSES = ("OPEN", "PARTIAL", "AUTHORISED", "CANCELLED", "CLOSED")
APPROVABLE_STATUSES = ("APPROVED", "PARTIALLY_APPROVED")
MOVEMENT_TYPES = ("INITIAL", "RECEIPT", "ISSUE", "ADJUSTMENT_IN", "ADJUSTMENT_OUT", "RETURN", "REVERSAL")
MOVEMENT_DIRECTIONS = ("IN", "OUT")
RESERVATION_STATUSES = ("ACTIVE", "CONSUMED", "RELEASED", "EXPIRED")
PURCHASE_ORDER_STATUSES = ("DRAFT", "APPROVED", "SENT", "PARTIALLY_RECEIVED", "RECEIVED", "CLOSED", "CANCELLED")
DOCUMENT_TYPES = ("REQ", "AUTH", "OC", "GRN", "INV_MOV", "RES", "ADJ", "COST_POST")
