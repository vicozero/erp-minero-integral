import type { User } from '../api/types';

// Cada entrada incluye el código heredado (inglés) y el alias en español que
// el backend almacena. El frontend solo oculta menús: la autorización real
// siempre se comprueba de nuevo en el servidor.
export const PERM = {
  VIEW_REQUISITIONS: ['requisition.view', 'requisiciones.ver_propias'],
  APPROVE_REQUISITIONS: ['requisition.approve', 'requisiciones.autorizar'],
  VIEW_HISTORY: ['requisition.history.view', 'requisiciones.historial'],
  VIEW_INVENTORY: ['inventory.availability.view', 'almacenes.consultar'],
  OPERATE_WAREHOUSE: ['inventory.reserve', 'almacenes.reservar'],
  VIEW_PURCHASES: ['purchase.view', 'compras.consultar'],
  CREATE_PURCHASES: ['purchase.order.create', 'compras.crear'],
  ADMIN_USERS: ['admin.users.manage', 'usuarios.administrar'],
  VIEW_AUDIT: ['audit.view', 'auditoria.consultar'],
  VIEW_CATALOG: ['catalog.view', 'catalogo.consultar'],
  MANAGE_CATALOG: ['catalog.manage', 'catalogo.administrar'],
  VIEW_LOCATIONS: ['warehouse.location.view', 'ubicaciones.consultar'],
  MANAGE_LOCATIONS: ['warehouse.location.manage', 'ubicaciones.administrar'],
  VIEW_MAPS: ['warehouse.map.view', 'mapas.almacen.consultar'],
  MANAGE_MAPS: ['warehouse.map.manage', 'mapas.almacen.administrar'],
  VIEW_STOCK_COST: ['warehouse.stock.view', 'almacenes.kardex'],
  VIEW_VOUCHERS: ['document.render', 'documentos.generar'],
  CREATE_VOUCHERS: ['warehouse.voucher.create', 'vales.crear'],
  ISSUE_VOUCHERS: ['warehouse.voucher.issue', 'vales.emitir'],
  VIEW_SLA: ['sla.view', 'semaforo.consultar'],
  VIEW_TRACE: ['requisition.history.view', 'requisiciones.historial'],
} as const;

export function can(user: User | null, ...codes: readonly string[]): boolean {
  if (!user) return false;
  return codes.some((code) => user.permissions.includes(code));
}

export function canAny(user: User | null, groups: readonly (readonly string[])[]): boolean {
  return groups.some((codes) => can(user, ...codes));
}
