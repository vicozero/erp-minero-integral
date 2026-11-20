import { loadEnv } from 'vite';
import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => {
  // GitHub Pages sirve el sitio de proyecto bajo /<nombre-del-repo>/.
  // La intranet operativa sirve dist/ desde la raíz, que es el valor por defecto.
  const base = loadEnv(mode, '.', 'VITE_').VITE_PUBLIC_BASE || '/';

  return {
    plugins: [react()],
    base,
    // Solo desarrollo local. La intranet operativa usa la compilación en dist/
    // servida por el proxy inverso; este servidor no debe publicarse en red.
    server: {
      host: '127.0.0.1',
      port: 5173,
      proxy: {
        '/api': 'http://127.0.0.1:8000',
        '/health': 'http://127.0.0.1:8000',
        '/status': 'http://127.0.0.1:8000',
        '/docs': 'http://127.0.0.1:8000',
        '/openapi.json': 'http://127.0.0.1:8000',
      },
    },
    test: {
      environment: 'jsdom',
      globals: true,
      setupFiles: ['./src/test/setup.ts'],
    },
  };
});
