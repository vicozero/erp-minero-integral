import { Suspense, useEffect, useMemo } from 'react';
import { Canvas, useThree } from '@react-three/fiber';
import { Html, OrbitControls } from '@react-three/drei';
import { TYPE_LABELS } from './constants';
import type { CameraPreset, PlanElement } from './types';

export interface Designer3DProps {
  elements: PlanElement[];
  width: number;
  height: number;
  selectedIds: string[];
  showWalls: boolean;
  cameraPreset: CameraPreset;
  resetToken: number;
  onSelect: (ids: string[]) => void;
}

const SCALE = 0.02;

function CameraRig({ preset, resetToken }: { preset: CameraPreset; resetToken: number }) {
  const { camera, controls } = useThree();
  useEffect(() => {
    const positions: Record<CameraPreset, [number, number, number]> = {
      orbit: [10, 9, 12],
      top: [0, 22, 0.01],
      isometric: [12, 12, 12],
      front: [0, 5, 20],
      aisle: [0, 3, 9],
    };
    const [x, y, z] = positions[preset];
    camera.position.set(x, y, z);
    camera.lookAt(0, 0, 0);
    const orbit = controls as { target?: { set: (x: number, y: number, z: number) => void }; update?: () => void } | null;
    orbit?.target?.set(0, 0, 0);
    orbit?.update?.();
  }, [camera, controls, preset, resetToken]);
  return null;
}

function ElementMesh({
  element,
  planWidth,
  planHeight,
  selected,
  onSelect,
}: {
  element: PlanElement;
  planWidth: number;
  planHeight: number;
  selected: boolean;
  onSelect: (id: string) => void;
}) {
  const x = (element.x + element.width / 2 - planWidth / 2) * SCALE;
  const z = (element.y + element.height / 2 - planHeight / 2) * SCALE;
  const vertical = element.type === 'WALL' ? 2.2 : element.type === 'RACK' ? Math.max(1, Number(element.depth ?? 2)) : 0.45;
  const footprintX = Math.max(0.08, element.width * SCALE);
  const footprintZ = Math.max(0.08, element.height * SCALE);
  const color = selected ? '#f43f5e' : element.color;
  return (
    <group position={[x, 0, z]}>
      <mesh
        position={[0, vertical / 2, 0]}
        onClick={(event) => {
          event.stopPropagation();
          onSelect(element.id);
        }}
      >
        <boxGeometry args={[footprintX, vertical, footprintZ]} />
        <meshStandardMaterial color={color} transparent opacity={element.type === 'ZONE' || element.type === 'AISLE' ? 0.25 : 0.85} />
      </mesh>
      <Html center position={[0, vertical + 0.35, 0]} distanceFactor={14}>
        <button
          type="button"
          data-designer-element-3d={element.id}
          className={`scene-label scene-label-button ${selected ? 'is-selected' : ''}`}
          onClick={() => onSelect(element.id)}
          title={`Seleccionar ${TYPE_LABELS[element.type]}`}
        >
          {element.code || element.name}
        </button>
      </Html>
    </group>
  );
}

export default function Designer3D({
  elements,
  width,
  height,
  selectedIds,
  showWalls,
  cameraPreset,
  resetToken,
  onSelect,
}: Designer3DProps) {
  const visible = useMemo(
    () => elements.filter((element) => element.visible && (showWalls || element.type !== 'WALL')),
    [elements, showWalls],
  );
  return (
    <Canvas camera={{ position: [10, 9, 12], fov: 45 }} shadows dpr={[1, 1.75]}>
      <Suspense fallback={null}>
        <color attach="background" args={['#0f172a']} />
        <ambientLight intensity={0.7} />
        <directionalLight position={[10, 18, 8]} intensity={1.1} castShadow />
        <gridHelper args={[Math.max(20, width * SCALE), 30, '#334155', '#1e293b']} />
        {visible.map((element) => (
          <ElementMesh
            key={element.id}
            element={element}
            planWidth={width}
            planHeight={height}
            selected={selectedIds.includes(element.id)}
            onSelect={(id) => onSelect([id])}
          />
        ))}
        <OrbitControls makeDefault enablePan enableZoom enableRotate maxPolarAngle={Math.PI / 2.05} />
        <CameraRig preset={cameraPreset} resetToken={resetToken} />
      </Suspense>
    </Canvas>
  );
}
