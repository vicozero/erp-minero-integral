/** Parámetros referenciales de la escena 3D; no son medidas físicas. */
export interface GeometrySettings {
  rackWidth: number;
  rackDepth: number;
  levelHeight: number;
  boxSize: number;
}

export const DEFAULT_GEOMETRY: GeometrySettings = {
  rackWidth: 3.2,
  rackDepth: 2.4,
  levelHeight: 1.1,
  boxSize: 0.85,
};
