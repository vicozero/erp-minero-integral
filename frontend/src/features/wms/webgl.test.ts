import { afterEach, describe, expect, it, vi } from 'vitest';
import { webglAvailable } from './webgl';

describe('Detección de WebGL', () => {
  afterEach(() => vi.restoreAllMocks());

  it('libera el contexto de prueba', () => {
    const loseContext = vi.fn();
    vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue({
      getExtension: () => ({ loseContext }),
    } as unknown as WebGLRenderingContext);

    expect(webglAvailable()).toBe(true);
    expect(loseContext).toHaveBeenCalledTimes(1);
  });

  it('devuelve false cuando no hay contexto', () => {
    vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(null);
    expect(webglAvailable()).toBe(false);
  });
});
