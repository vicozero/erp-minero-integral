import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';
import type { User } from '../../api/types';
import { AuthProvider } from '../../auth/AuthContext';
import { PasswordChangeForm } from './ChangePassword';

const user: User = {
  id: '22222222-2222-2222-2222-222222222222',
  username: 'demo.solicitante',
  email: 'solicitante.demo@example.invalid',
  full_name: 'Solicitante Demo',
  status: 'ACTIVE',
  roles: ['SOLICITANTE'],
  permissions: [],
  department_ids: [],
  must_change_password: true,
};

describe('Política de contraseña en el cambio', () => {
  it('indica y permite un mínimo de 6 caracteres', () => {
    render(
      <MemoryRouter>
        <AuthProvider initialUser={user}>
          <PasswordChangeForm />
        </AuthProvider>
      </MemoryRouter>,
    );

    expect(screen.getByText(/Mínimo 6 caracteres/i)).toBeInTheDocument();
    expect(screen.getByLabelText('Contraseña nueva')).toHaveAttribute('minLength', '6');
    expect(screen.getByLabelText('Confirmar contraseña nueva')).toHaveAttribute('minLength', '6');
  });
});
