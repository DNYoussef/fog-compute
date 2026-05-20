'use client';

import { Component, ReactNode, useMemo, useRef } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { OrbitControls, Sphere, Line } from '@react-three/drei';
import * as THREE from 'three';

interface MixnodeInfo {
  id: string;
  position: { x: number; y: number; z: number };
  status: 'active' | 'inactive' | 'degraded';
  reputation: number;
}

interface NetworkNodeProps {
  node: MixnodeInfo;
  isSelected: boolean;
  onClick: () => void;
}

function NetworkNode({ node, isSelected, onClick }: NetworkNodeProps) {
  const meshRef = useRef<THREE.Mesh>(null);

  useFrame((state) => {
    if (meshRef.current) {
      meshRef.current.rotation.y += 0.01;
      if (isSelected) {
        meshRef.current.scale.setScalar(1 + Math.sin(state.clock.elapsedTime * 3) * 0.1);
      }
    }
  });

  const color = useMemo(() => {
    if (node.status === 'active') return '#10b981';
    if (node.status === 'degraded') return '#f59e0b';
    return '#ef4444';
  }, [node.status]);

  return (
    <Sphere
      ref={meshRef}
      args={[0.3, 32, 32]}
      position={[node.position.x, node.position.y, node.position.z]}
      onClick={onClick}
    >
      <meshStandardMaterial
        color={color}
        emissive={color}
        emissiveIntensity={isSelected ? 0.5 : 0.2}
        transparent
        opacity={0.8}
      />
    </Sphere>
  );
}

function NetworkConnections({ mixnodes }: { mixnodes: MixnodeInfo[] }) {
  const lines = useMemo(() => {
    const connections = [];
    for (let i = 0; i < mixnodes.length; i++) {
      for (let j = i + 1; j < mixnodes.length; j++) {
        const distance = Math.sqrt(
          Math.pow(mixnodes[i].position.x - mixnodes[j].position.x, 2) +
          Math.pow(mixnodes[i].position.y - mixnodes[j].position.y, 2) +
          Math.pow(mixnodes[i].position.z - mixnodes[j].position.z, 2)
        );
        if (distance < 5) {
          connections.push({
            start: [mixnodes[i].position.x, mixnodes[i].position.y, mixnodes[i].position.z],
            end: [mixnodes[j].position.x, mixnodes[j].position.y, mixnodes[j].position.z],
          });
        }
      }
    }
    return connections;
  }, [mixnodes]);

  return (
    <>
      {lines.map((line, index) => (
        <Line
          key={index}
          points={[line.start as [number, number, number], line.end as [number, number, number]]}
          color="#06b6d4"
          lineWidth={1}
          transparent
          opacity={0.3}
        />
      ))}
    </>
  );
}

interface BetanetTopologyProps {
  mixnodes: MixnodeInfo[];
  selectedNode: string | null;
  onNodeSelect: (nodeId: string) => void;
}

interface WebGLErrorBoundaryProps {
  children: ReactNode;
  fallback: ReactNode;
}

interface WebGLErrorBoundaryState {
  hasError: boolean;
}

class WebGLErrorBoundary extends Component<WebGLErrorBoundaryProps, WebGLErrorBoundaryState> {
  state: WebGLErrorBoundaryState = { hasError: false };

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error: Error) {
    console.warn('Betanet topology WebGL unavailable:', error.message);
  }

  render() {
    if (this.state.hasError) {
      return this.props.fallback;
    }

    return this.props.children;
  }
}

function TopologyFallback({
  mixnodes,
  selectedNode,
  onNodeSelect,
}: BetanetTopologyProps) {
  return (
    <div
      className="flex h-full min-h-[320px] flex-col justify-center rounded-lg border border-white/10 bg-black/20 p-6"
      data-testid="betanet-topology-fallback"
    >
      <div className="mb-4">
        <h3 className="text-lg font-semibold text-fog-cyan">Topology Map</h3>
        <p className="text-sm text-gray-400">WebGL is unavailable in this browser session.</p>
      </div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {mixnodes.map((node) => (
          <button
            key={node.id}
            type="button"
            onClick={() => onNodeSelect(node.id)}
            data-testid={`topology-fallback-node-${node.id}`}
            className={`rounded-lg border p-3 text-left transition-colors ${
              selectedNode === node.id
                ? 'border-fog-cyan bg-fog-cyan/10'
                : 'border-white/10 bg-white/5 hover:bg-white/10'
            }`}
          >
            <div className="mb-2 flex items-center gap-2">
              <span
                className={`h-2 w-2 rounded-full ${
                  node.status === 'active'
                    ? 'bg-green-400'
                    : node.status === 'degraded'
                      ? 'bg-yellow-400'
                      : 'bg-red-400'
                }`}
              />
              <span className="font-mono text-sm text-white">{node.id.substring(0, 12)}...</span>
            </div>
            <div className="text-xs text-gray-400">
              Reputation {Math.round(node.reputation * 100)}%
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}

export function BetanetTopology({ mixnodes, selectedNode, onNodeSelect }: BetanetTopologyProps) {
  const fallback = (
    <TopologyFallback
      mixnodes={mixnodes}
      selectedNode={selectedNode}
      onNodeSelect={onNodeSelect}
    />
  );

  return (
    <div className="w-full h-full" data-testid="betanet-topology">
      <WebGLErrorBoundary fallback={fallback}>
        <Canvas camera={{ position: [0, 0, 15], fov: 60 }} fallback={fallback}>
          <ambientLight intensity={0.5} />
          <pointLight position={[10, 10, 10]} intensity={1} />
          <pointLight position={[-10, -10, -10]} intensity={0.5} />

          {mixnodes.map((node) => (
            <NetworkNode
              key={node.id}
              node={node}
              isSelected={selectedNode === node.id}
              onClick={() => onNodeSelect(node.id)}
            />
          ))}

          <NetworkConnections mixnodes={mixnodes} />

          <OrbitControls
            enableZoom={true}
            enablePan={true}
            enableRotate={true}
            autoRotate={true}
            autoRotateSpeed={0.5}
          />
        </Canvas>
      </WebGLErrorBoundary>
    </div>
  );
}
