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

PERMISSIONS: tuple[str, ...] = PERMISSIONS_LEGACY + PERMISSIONS_FASE3 + PERMISSIONS_INTERNAL

# Alias español -> código canónico heredado. Permite que una política escrita
# con un código u otro se resuelva a la misma comprobación.
PERMISSION_ALIASES: dict[str, str] = {
    "requisiciones.crear": "requisition.create",
    "requisiciones.autorizar": "requisition.approve",
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
    "requisition.view",
    "requisition.view_department",
    "requisition.history.view",
    "inventory.availability.view",
    "requisiciones.autorizar",
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

ROLE_PERMISSIONS: dict[str, tuple[str, ...]] = {
    "ADMIN": PERMISSIONS,
    "SOLICITANTE": _SOLICITANTE,
    "JEFE_DEPARTAMENTO": _SOLICITANTE + _APROBADOR + ("departamentos.consultar",),
    "APROBADOR": _APROBADOR,
    "ALMACENISTA": _ALMACEN,
    "ALMACEN": _ALMACEN,
    "COMPRADOR": _COMPRAS,
    "COMPRAS": _COMPRAS,
    "GERENCIA": _LECTURA + ("audit.view", "auditoria.consultar", "sesiones.consultar"),
    "AUDITOR": _LECTURA + ("audit.view", "auditoria.consultar", "usuarios.consultar"),
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

REQUISITION_STATUSES = ("DRAFT", "SUBMITTED", "APPROVED", "PARTIALLY_APPROVED", "REJECTED", "CANCELLED", "IN_PROGRESS", "CLOSED")
REQUISITION_LINE_STATUSES = ("OPEN", "PARTIAL", "AUTHORISED", "CANCELLED", "CLOSED")
APPROVABLE_STATUSES = ("APPROVED", "PARTIALLY_APPROVED")
MOVEMENT_TYPES = ("INITIAL", "RECEIPT", "ISSUE", "ADJUSTMENT_IN", "ADJUSTMENT_OUT", "RETURN", "REVERSAL")
MOVEMENT_DIRECTIONS = ("IN", "OUT")
RESERVATION_STATUSES = ("ACTIVE", "CONSUMED", "RELEASED", "EXPIRED")
PURCHASE_ORDER_STATUSES = ("DRAFT", "APPROVED", "SENT", "PARTIALLY_RECEIVED", "RECEIVED", "CLOSED", "CANCELLED")
DOCUMENT_TYPES = ("REQ", "AUTH", "OC", "GRN", "INV_MOV", "RES", "ADJ", "COST_POST")
