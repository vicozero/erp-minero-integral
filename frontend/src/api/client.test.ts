import { afterEach, describe, expect, it, vi } from 'vitest';
import { api, setCsrfToken } from './client';

function mockFetch(status = 204) {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, status });
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

describe('Cliente API con cookies de sesión', () => {
  afterEach(() => {
    setCsrfToken(null);
    vi.unstubAllGlobals();
  });

  it('envía la cookie de sesión y el token CSRF en operaciones de escritura', async () => {
    setCsrfToken('csrf-de-prueba');
    const fetchMock = mockFetch();

    await api.logout();

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain('/api/v1/auth/logout');
    expect(init.credentials).toBe('include');
    expect(init.method).toBe('POST');
    const headers = new Headers(init.headers);
    expect(headers.get('X-CSRF-Token')).toBe('csrf-de-prueba');
  });

  it('no envía token CSRF en lecturas GET', async () => {
    const fetchMock = mockFetch(200);
    fetchMock.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ username: 'demo.admin' }),
    });

    await api.me();

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    const headers = new Headers(init.headers);
    expect(headers.has('X-CSRF-Token')).toBe(false);
    expect(init.credentials).toBe('include');
  });

  it('no guarda el token de sesión en almacenamiento local', () => {
    expect(window.localStorage.length).toBe(0);
  });
});
