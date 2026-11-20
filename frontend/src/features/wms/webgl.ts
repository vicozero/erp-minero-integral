/** Detecta WebGL sin importar Three.js (útil para el fallback 2D y pruebas). */
export function webglAvailable(): boolean {
  if (typeof document === 'undefined') return false;
  try {
    const canvas = document.createElement('canvas');
    const context = canvas.getContext('webgl2') ?? canvas.getContext('webgl');
    if (!context) return false;
    // La prueba consume uno de los contextos limitados del navegador. En
    // entornos simulados el contexto puede no exponer la extensión.
    const loseContext = context.getExtension?.('WEBGL_lose_context');
    loseContext?.loseContext();
    return true;
  } catch {
    return false;
  }
}
