import type { ReactNode } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { AuthProvider, useAuth } from './auth/AuthContext';
import { can, PERM } from './auth/permissions';
import { Layout } from './components/Layout';
import { Users } from './features/admin/Users';
import { Audit } from './features/audit/Audit';
import { AccessDenied } from './features/auth/AccessDenied';
import { ChangePassword } from './features/auth/ChangePassword';
import { Login } from './features/auth/Login';
import { Approvals } from './features/approvals/Approvals';
import { Catalog } from './features/catalog/Catalog';
import { Dashboard } from './features/dashboard/Dashboard';
import { History } from './features/history/History';
import { Inventory } from './features/inventory/Inventory';
import { Purchases } from './features/purchases/Purchases';
import { Requisitions } from './features/requisitions/Requisitions';
import { SlaBoard } from './features/sla/SlaBoard';
import { Traceability } from './features/trace/Traceability';
import { Vouchers } from './features/vouchers/Vouchers';
import { Locations } from './features/wms/Locations';
import { WarehouseInteractive } from './features/wms/WarehouseInteractive';
import { MyAccount } from './features/security/MyAccount';
import { Permissions, Roles } from './features/security/RolesAndPermissions';

function RequireAuth({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="boot-loading">Verificando sesión…</div>;
  return user ? <>{children}</> : <Navigate to="/login" replace />;
}

function RequirePermission({ codes, children }: { codes: readonly string[]; children: ReactNode }) {
  const { user } = useAuth();
  return can(user, ...codes) ? <>{children}</> : <Navigate to="/acceso-denegado" replace />;
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route
            element={
              <RequireAuth>
                <Layout />
              </RequireAuth>
            }
          >
            <Route index element={<Dashboard />} />
            <Route
              path="requisiciones"
              element={<RequirePermission codes={PERM.VIEW_REQUISITIONS}><Requisitions /></RequirePermission>}
            />
            <Route
              path="autorizaciones"
              element={<RequirePermission codes={PERM.APPROVE_REQUISITIONS}><Approvals /></RequirePermission>}
            />
            <Route
              path="almacen"
              element={<RequirePermission codes={PERM.VIEW_INVENTORY}><Inventory /></RequirePermission>}
            />
            <Route
              path="compras"
              element={<RequirePermission codes={PERM.VIEW_PURCHASES}><Purchases /></RequirePermission>}
            />
            <Route
              path="catalogo"
              element={<RequirePermission codes={PERM.VIEW_CATALOG}><Catalog /></RequirePermission>}
            />
            <Route
              path="almacen-virtual"
              element={<RequirePermission codes={PERM.VIEW_MAPS}><WarehouseInteractive /></RequirePermission>}
            />
            <Route
              path="ubicaciones"
              element={<RequirePermission codes={PERM.VIEW_LOCATIONS}><Locations /></RequirePermission>}
            />
            <Route
              path="vales"
              element={<RequirePermission codes={PERM.VIEW_VOUCHERS}><Vouchers /></RequirePermission>}
            />
            <Route
              path="semaforo"
              element={<RequirePermission codes={PERM.VIEW_SLA}><SlaBoard /></RequirePermission>}
            />
            <Route
              path="trazabilidad"
              element={<RequirePermission codes={PERM.VIEW_TRACE}><Traceability /></RequirePermission>}
            />
            <Route
              path="trazabilidad/:requisitionId"
              element={<RequirePermission codes={PERM.VIEW_TRACE}><Traceability /></RequirePermission>}
            />
            <Route
              path="historial"
              element={<RequirePermission codes={PERM.VIEW_HISTORY}><History /></RequirePermission>}
            />
            <Route
              path="usuarios"
              element={<RequirePermission codes={PERM.ADMIN_USERS}><Users /></RequirePermission>}
            />
            <Route
              path="auditoria"
              element={<RequirePermission codes={PERM.VIEW_AUDIT}><Audit /></RequirePermission>}
            />
            <Route path="mi-cuenta" element={<MyAccount />} />
            <Route
              path="roles"
              element={<RequirePermission codes={PERM.ADMIN_USERS}><Roles /></RequirePermission>}
            />
            <Route
              path="permisos"
              element={<RequirePermission codes={PERM.ADMIN_USERS}><Permissions /></RequirePermission>}
            />
            <Route path="cambiar-contraseña" element={<ChangePassword />} />
            <Route path="acceso-denegado" element={<AccessDenied />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
