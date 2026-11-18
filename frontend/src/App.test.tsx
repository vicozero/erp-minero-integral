import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';
import { AuthProvider } from './auth/AuthContext';
import { Login } from './features/auth/Login';

describe('Pantalla de acceso', () => {
  it('muestra el formulario con las cuentas ficticias disponibles', () => {
    render(
      <MemoryRouter>
        <AuthProvider>
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
