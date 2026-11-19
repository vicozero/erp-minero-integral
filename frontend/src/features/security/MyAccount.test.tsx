import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { api } from '../../api/client';
import type { Session, User } from '../../api/types';
import { AuthProvider } from '../../auth/AuthContext';
import { MyAccount } from './MyAccount';

const admin: User = {
  id: 'user-1',
  username: 'admin',
  email: 'admin@erp.local.invalid',
  full_name: 'Superadministrador del ERP',
  status: 'ACTIVE',
  roles: ['SUPERADMIN'],
  permissions: ['admin.users.manage', 'roles.asignar', 'usuarios.administrar'],
  department_ids: [],
  must_change_password: false,
};

const session: Session = {
  id: 'session-1',
  user_id: admin.id,
  created_at: '2026-11-19T12:00:00Z',
  expires_at: '2026-11-19T13:00:00Z',
  last_seen_at: '2026-11-19T12:10:00Z',
  revoked_at: null,
};

function renderAccount(user: User = admin) {
  return render(
    <MemoryRouter>
      <AuthProvider initialUser={user}>
        <MyAccount />
      </AuthProvider>
    </MemoryRouter>,
  );
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe('Administración · Seguridad · Mi cuenta', () => {
  it('muestra identificación, contraseña y sesiones activas', async () => {
    vi.spyOn(api, 'mySessions').mockResolvedValue([session]);
    renderAccount();

    expect(screen.getByRole('heading', { name: 'Mi cuenta' })).toBeInTheDocument();
    expect(screen.getByLabelText('Nombre de usuario')).toHaveValue('admin');
    expect(screen.getByLabelText('Contraseña actual para cambiar usuario')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /Contraseña/ })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText(/6:00/)).toBeInTheDocument());
  });

  it('actualiza el nombre de usuario exigiendo la contraseña actual', async () => {
    vi.spyOn(api, 'mySessions').mockResolvedValue([]);
    const change = vi.spyOn(api, 'changeUsername').mockResolvedValue({
      ...admin,
      username: 'admin.seguro',
    });
    renderAccount();

    fireEvent.change(screen.getByLabelText('Nombre de usuario'), {
      target: { value: 'admin.seguro' },
    });
    fireEvent.change(screen.getByLabelText('Contraseña actual para cambiar usuario'), {
      target: { value: 'ClaveActual123!' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Actualizar usuario' }));

    await waitFor(() => {
      expect(change).toHaveBeenCalledWith('admin.seguro', 'ClaveActual123!');
    });
    await waitFor(() => {
      expect(screen.getByLabelText('Nombre de usuario')).toHaveValue('admin.seguro');
    });
  });
});
