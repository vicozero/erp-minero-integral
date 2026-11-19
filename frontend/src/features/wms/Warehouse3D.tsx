import { Suspense, useEffect, useMemo, useRef } from 'react';
import { Canvas, useThree } from '@react-three/fiber';
import { Html, OrbitControls } from '@react-three/drei';
import type { LocationMapNode } from '../../api/types';
import { formatNumber } from '../../components/ui';
import { occupancyTone, OCCUPANCY_LEGEND, type OccupancyTone } from './InteractiveMap2D';
import type { GeometrySettings } from './warehouse3dConfig';

const TONE_COLORS: Record<OccupancyTone, string> = {
  empty: '#94a3b8',
  low: '#22c55e',
  medium: '#f59e0b',
  high: '#ef4444',
  blocked: '#64748b',
};

export interface Warehouse3DProps {
  nodes: LocationMapNode[];
  width: string;
  height: string;
  selectedId: string | null;
  highlightIds: string[];
  detailed: boolean;
  resetToken: number;
  geometry: GeometrySettings;
  onSelect: (locationId: string) => void;
}

type PlacedNode = {
  node: LocationMapNode;
  x: number;
  z: number;
  y: number;
  tone: OccupancyTone;
};

function usePlacedNodes(nodes: LocationMapNode[], width: number, height: number, levelHeight: number): PlacedNode[] {
  return useMemo(() => {
    const levels = Array.from(new Set(nodes.map((node) => node.level).filter(Boolean))).sort();
    const scale = 0.02;
    return nodes
      .filter((node) => node.coord_x !== null && node.coord_y !== null)
      .map((node) => {
        const levelIndex = Math.max(0, levels.indexOf(node.level ?? ''));
        return {
          node,
          x: (Number(node.coord_x) - width / 2) * scale,
          z: (Number(node.coord_y) - height / 2) * scale,
          y: levelIndex * levelHeight + 0.45,
          tone: occupancyTone(node),
        };
      });
  }, [nodes, width, height, levelHeight]);
}

function CameraRig({ resetToken }: { resetToken: number }) {
  const { camera, controls } = useThree();
  const initial = useRef(true);
  useEffect(() => {
    if (initial.current) {
      initial.current = false;
      return;
    }
    camera.position.set(9, 8, 11);
    camera.lookAt(0, 0, 0);
    const orbit = controls as { target?: { set: (x: number, y: number, z: number) => void }; update?: () => void } | null;
    orbit?.target?.set(0, 0, 0);
    orbit?.update?.();
  }, [camera, controls, resetToken]);
  return null;
}

function RackFrame({
  x,
  z,
  topY,
  width,
  depth,
  label,
  selected,
  locationId,
  onSelect,
}: {
  x: number;
  z: number;
  topY: number;
  width: number;
  depth: number;
  label: string;
  selected: boolean;
  locationId: string;
  onSelect: (locationId: string) => void;
}) {
  const posts: Array<[number, number]> = [
    [-1, -1],
    [1, -1],
    [-1, 1],
    [1, 1],
  ];
  const postColor = selected ? '#38bdf8' : '#64748b';
  return (
    <group position={[x, 0, z]}>
      {posts.map(([px, pz]) => (
        <mesh key={`${px}-${pz}`} position={[(px * width) / 2, topY / 2, (pz * depth) / 2]}>
          <boxGeometry args={[0.09, topY, 0.09]} />
          <meshStandardMaterial color={postColor} metalness={0.35} roughness={0.6} />
        </mesh>
      ))}
      <Html center position={[0, topY + 0.5, 0]} distanceFactor={12}>
        <button
          type="button"
          data-rack-id={label}
          className={`scene-label scene-label-button ${selected ? 'is-selected' : ''}`}
          title={`Seleccionar rack ${label}`}
          onClick={() => onSelect(locationId)}
        >
          {label}
        </button>
      </Html>
    </group>
  );
}

function PositionBox({
  placed,
  detailed,
  selected,
  highlighted,
  boxSize,
  onSelect,
}: {
  placed: PlacedNode;
  detailed: boolean;
  selected: boolean;
  highlighted: boolean;
  boxSize: number;
  onSelect: (locationId: string) => void;
}) {
  const { node, x, y, z, tone } = placed;
  const color = TONE_COLORS[tone];
  const occupied = Number(node.occupied_qty) > 0;
  return (
    <group position={[x, y, z]}>
      <mesh
        onClick={(event) => {
          event.stopPropagation();
          onSelect(node.id);
        }}
      >
        <boxGeometry args={occupied ? [boxSize, boxSize * 0.8, boxSize] : [boxSize, 0.08, boxSize]} />
        <meshStandardMaterial
          color={color}
          emissive={selected || highlighted ? '#38bdf8' : '#000000'}
          emissiveIntensity={selected ? 0.85 : highlighted ? 0.5 : 0}
          transparent={!occupied}
          opacity={occupied ? 0.92 : 0.35}
        />
      </mesh>
      {detailed && (
        <Html center position={[0, boxSize * 1.1, 0]} distanceFactor={10}>
          <button
            type="button"
            data-location-id={node.id}
            className={`scene-label scene-label-button ${selected ? 'is-selected' : ''}`}
            onClick={() => onSelect(node.id)}
          >
            {node.code} · {formatNumber(node.occupied_qty)}
          </button>
        </Html>
      )}
    </group>
  );
}

function Scene({
  nodes,
  width,
  height,
  selectedId,
  highlightIds,
  detailed,
  geometry,
  resetToken,
  onSelect,
}: Warehouse3DProps) {
  const placed = usePlacedNodes(nodes, Number(width) || 1000, Number(height) || 600, geometry.levelHeight);
  const racks = useMemo(() => {
    const groups = new Map<string, PlacedNode[]>();
    placed.forEach((item) => {
      if (!item.node.rack) return;
      const key = `${item.node.zone ?? ''}|${item.node.aisle ?? ''}|${item.node.rack}`;
      groups.set(key, [...(groups.get(key) ?? []), item]);
    });
    return Array.from(groups.entries()).map(([key, items]) => {
      const xs = items.map((item) => item.x);
      const zs = items.map((item) => item.z);
      return {
        key,
        x: (Math.min(...xs) + Math.max(...xs)) / 2,
        z: (Math.min(...zs) + Math.max(...zs)) / 2,
        topY: Math.max(...items.map((item) => item.y)) + geometry.levelHeight,
        selected: items.some((item) => item.node.id === selectedId),
        locationId: items[0].node.id,
      };
    });
  }, [placed, geometry.levelHeight, selectedId]);

  const zoneNodes = placed.filter((item) => !item.node.rack);

  return (
    <>
      <color attach="background" args={['#0f172a']} />
      <ambientLight intensity={0.8} />
      <directionalLight position={[6, 12, 8]} intensity={1.1} />
      <gridHelper args={[24, 24, '#475569', '#1e293b']} />
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.02, 0]} receiveShadow>
        <planeGeometry args={[24, 24]} />
        <meshStandardMaterial color="#162032" roughness={0.9} />
      </mesh>

      {racks.map((rack) => (
        <RackFrame
          key={rack.key}
          x={rack.x}
          z={rack.z}
          topY={rack.topY}
          width={geometry.rackWidth}
          depth={geometry.rackDepth}
          label={rack.key.split('|').filter(Boolean).join(' / ')}
          selected={rack.selected}
          locationId={rack.locationId}
          onSelect={onSelect}
        />
      ))}

      {zoneNodes.map((item) => (
        <group key={item.node.id} position={[item.x, 0.05, item.z]}>
          <mesh
            onClick={(event) => {
              event.stopPropagation();
              onSelect(item.node.id);
            }}
          >
            <boxGeometry args={[geometry.rackDepth, 0.1, geometry.rackDepth]} />
            <meshStandardMaterial color={TONE_COLORS[item.tone]} transparent opacity={0.65} />
          </mesh>
          {detailed && (
            <Html center position={[0, 0.6, 0]} distanceFactor={10}>
              <button
                type="button"
                data-location-id={item.node.id}
                className={`scene-label scene-label-button ${selectedId === item.node.id ? 'is-selected' : ''}`}
                onClick={() => onSelect(item.node.id)}
              >
                {item.node.code}
              </button>
            </Html>
          )}
        </group>
      ))}

      {placed
        .filter((item) => item.node.rack)
        .map((item) => (
          <PositionBox
            key={item.node.id}
            placed={item}
            detailed={detailed}
            selected={selectedId === item.node.id}
            highlighted={highlightIds.includes(item.node.id)}
            boxSize={geometry.boxSize}
            onSelect={onSelect}
          />
        ))}

      <OrbitControls makeDefault enablePan enableZoom enableRotate minDistance={3} maxDistance={40} maxPolarAngle={Math.PI / 2.05} />
      <CameraRig resetToken={resetToken} />
    </>
  );
}

export default function Warehouse3D(props: Warehouse3DProps) {
  return (
    <div className="scene-3d" data-testid="mapa-3d">
      <Canvas camera={{ position: [9, 8, 11], fov: 50 }} dpr={[1, 1.5]}>
        <Suspense fallback={null}>
          <Scene {...props} />
        </Suspense>
      </Canvas>
      <div className="scene-hint">
        Arrastre para rotar · rueda para acercar · clic derecho para mover · seleccione una posición
      </div>
      <div className="map-legend scene-legend" aria-label="Leyenda de ocupación 3D">
        {OCCUPANCY_LEGEND.map((item) => (
          <span key={item.tone} className="legend-item">
            <i className={`legend-swatch map-tone-${item.tone}`} aria-hidden="true" /> {item.label}
          </span>
        ))}
      </div>
    </div>
  );
}
