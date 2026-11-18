PERMISSIONS: tuple[str, ...] = (
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

ROLE_PERMISSIONS: dict[str, tuple[str, ...]] = {
    "ADMIN": PERMISSIONS,
    "SOLICITANTE": (
        "requisition.create",
        "requisition.submit",
        "requisition.view",
        "requisition.history.view",
        "inventory.availability.view",
    ),
    "APROBADOR": (
        "requisition.approve",
        "requisition.view",
        "requisition.history.view",
        "inventory.availability.view",
    ),
    "ALMACENISTA": (
        "inventory.availability.view",
        "inventory.reserve",
        "inventory.issue",
        "inventory.kardex.view",
        "requisition.view",
        "requisition.history.view",
        "purchase.view",
    ),
    "COMPRADOR": (
        "purchase.order.create",
        "purchase.order.approve",
        "purchase.receive",
        "purchase.view",
        "inventory.availability.view",
        "requisition.view",
        "requisition.history.view",
    ),
}

REQUISITION_STATUSES = ("DRAFT", "SUBMITTED", "APPROVED", "PARTIALLY_APPROVED", "REJECTED", "CANCELLED", "IN_PROGRESS", "CLOSED")
REQUISITION_LINE_STATUSES = ("OPEN", "PARTIAL", "AUTHORISED", "CANCELLED", "CLOSED")
APPROVABLE_STATUSES = ("APPROVED", "PARTIALLY_APPROVED")
MOVEMENT_TYPES = ("INITIAL", "RECEIPT", "ISSUE", "ADJUSTMENT_IN", "ADJUSTMENT_OUT", "RETURN", "REVERSAL")
MOVEMENT_DIRECTIONS = ("IN", "OUT")
RESERVATION_STATUSES = ("ACTIVE", "CONSUMED", "RELEASED", "EXPIRED")
PURCHASE_ORDER_STATUSES = ("DRAFT", "APPROVED", "SENT", "PARTIALLY_RECEIVED", "RECEIVED", "CLOSED", "CANCELLED")
DOCUMENT_TYPES = ("REQ", "AUTH", "OC", "GRN", "INV_MOV", "RES", "ADJ", "COST_POST")
