import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';
import type { User } from './api/types';
import { AuthProvider } from './auth/AuthContext';
import { Layout } from './components/Layout';
import { Login } from './features/auth/Login';

function makeUser(overrides: Partial<User> = {}): User {
  return {
    id: '11111111-1111-1111-1111-111111111111',
    username: 'demo.solicitante',
    email: 'solicitante.demo@example.invalid',
    full_name: 'Solicitante Demo',
    status: 'ACTIVE',
    roles: ['SOLICITANTE'],
    permissions: ['requisition.view', 'requisition.create', 'requisiciones.ver_propias'],
    department_ids: [],
    must_change_password: false,
    ...overrides,
  };
}

function renderLayout(user: User) {
  return render(
    <MemoryRouter>
      <AuthProvider initialUser={user}>
        <Layout />
      </AuthProvider>
    </MemoryRouter>,
  );
}

describe('Pantalla de acceso', () => {
  it('muestra el formulario con las cuentas ficticias disponibles', () => {
    render(
      <MemoryRouter>
        <AuthProvider initialUser={null}>
          <Login />
        </AuthProvider>
      </MemoryRouter>,
    );

    expect(screen.getByRole('heading', { name: /ERP MINERO INTEGRAL/i })).toBeInTheDocument();
    expect(screen.getByLabelText('Usuario')).toHaveValue('demo.solicitante');
    expect(screen.getByLabelText('Contraseña')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Ingresar' })).toBeInTheDocument();
  });
});

describe('Menú por permisos', () => {
  it('oculta las secciones administrativas a un solicitante', () => {
    renderLayout(makeUser());

    expect(screen.getByRole('link', { name: /Requisiciones/ })).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: /Usuarios/ })).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: /Auditoría/ })).not.toBeInTheDocument();
  });

  it('muestra administración y auditoría a un usuario con esos permisos', () => {
    renderLayout(
      makeUser({
        username: 'demo.admin',
        roles: ['ADMIN'],
        permissions: ['admin.users.manage', 'audit.view', 'requisition.view'],
      }),
    );

    expect(screen.getByRole('link', { name: /Usuarios/ })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Auditoría/ })).toBeInTheDocument();
  });

  it('advierte cuando la cuenta requiere cambio de contraseña', () => {
    renderLayout(makeUser({ must_change_password: true }));
    expect(screen.getByRole('status')).toHaveTextContent(/contraseña.*temporal/i);
  });
});
