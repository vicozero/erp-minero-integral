import type { ReactNode } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { AuthProvider, useAuth } from './auth/AuthContext';
import { Layout } from './components/Layout';
import { Login } from './features/auth/Login';
import { Approvals } from './features/approvals/Approvals';
import { Dashboard } from './features/dashboard/Dashboard';
import { History } from './features/history/History';
import { Inventory } from './features/inventory/Inventory';
import { Purchases } from './features/purchases/Purchases';
import { Requisitions } from './features/requisitions/Requisitions';

function RequireAuth({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  return user ? <>{children}</> : <Navigate to="/login" replace />;
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
            <Route path="requisiciones" element={<Requisitions />} />
            <Route path="autorizaciones" element={<Approvals />} />
            <Route path="almacen" element={<Inventory />} />
            <Route path="compras" element={<Purchases />} />
            <Route path="historial" element={<History />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
