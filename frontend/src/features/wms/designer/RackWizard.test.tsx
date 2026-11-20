import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { RackWizard } from './RackWizard';

describe('Asistente de rack', () => {
  it('no solicita ubicaciones WMS cuando el actor carece del permiso', () => {
    const onConfirm = vi.fn();
    render(
      <RackWizard x={10} y={20} canManageLocations={false} onCancel={vi.fn()} onConfirm={onConfirm} />,
    );

    const checkbox = screen.getByLabelText('Crear/vincular ubicaciones WMS') as HTMLInputElement;
    expect(checkbox.disabled).toBe(true);
    expect(checkbox.checked).toBe(false);
    fireEvent.click(screen.getByRole('button', { name: 'Crear rack' }));
    expect(onConfirm.mock.calls[0][0]).toMatchObject({ create_locations: false, x: 10, y: 20 });
  });

  it('propone ubicaciones WMS sólo cuando el actor tiene el permiso', () => {
    const onConfirm = vi.fn();
    render(
      <RackWizard x={10} y={20} canManageLocations onCancel={vi.fn()} onConfirm={onConfirm} />,
    );

    const checkbox = screen.getByLabelText('Crear/vincular ubicaciones WMS') as HTMLInputElement;
    expect(checkbox.checked).toBe(true);
    fireEvent.click(screen.getByRole('button', { name: 'Crear rack' }));
    expect(onConfirm.mock.calls[0][0]).toMatchObject({ create_locations: true });
  });
});
