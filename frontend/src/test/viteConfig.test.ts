// @vitest-environment node
import { afterEach, describe, expect, it, vi } from 'vitest';
import config from '../../vite.config';

type ConfigFactory = (env: { mode: string }) => { base?: string };

describe('ruta base del frontend', () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it('sirve desde la raíz cuando no se define VITE_PUBLIC_BASE', () => {
    vi.stubEnv('VITE_PUBLIC_BASE', '');
    const base = (config as ConfigFactory)({ mode: 'production' }).base;
    expect(base).toBe('/');
  });

  it('sirve desde la ruta del proyecto cuando se define VITE_PUBLIC_BASE', () => {
    vi.stubEnv('VITE_PUBLIC_BASE', '/erp-minero-integral/');
    const base = (config as ConfigFactory)({ mode: 'production' }).base;
    expect(base).toBe('/erp-minero-integral/');
  });
});
