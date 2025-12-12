import React, { useRef } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { Sphere, OrbitControls } from '@react-three/drei';
import * as THREE from 'three';

interface WireframeSphereProps {
  speed?: number;
}

const WireframeSphere: React.FC<WireframeSphereProps> = ({ speed = 0.5 }) => {
  const meshRef = useRef<THREE.Mesh>(null);
  const innerMeshRef = useRef<THREE.Mesh>(null);

  useFrame((_, delta) => {
    if (meshRef.current) {
      meshRef.current.rotation.y += delta * speed;
      meshRef.current.rotation.x += delta * speed * 0.3;
    }
    if (innerMeshRef.current) {
      innerMeshRef.current.rotation.y -= delta * speed * 0.7;
      innerMeshRef.current.rotation.z += delta * speed * 0.5;
    }
  });

  return (
    <group>
      {/* Outer sphere */}
      <mesh ref={meshRef}>
        <sphereGeometry args={[1.5, 24, 24]} />
        <meshBasicMaterial
          color="#6b7280"
          wireframe
          transparent
          opacity={0.6}
        />
      </mesh>
      {/* Inner sphere rotating opposite direction */}
      <mesh ref={innerMeshRef}>
        <sphereGeometry args={[1.2, 16, 16]} />
        <meshBasicMaterial
          color="#9ca3af"
          wireframe
          transparent
          opacity={0.4}
        />
      </mesh>
      {/* Core glow */}
      <mesh>
        <sphereGeometry args={[0.3, 16, 16]} />
        <meshBasicMaterial color="#60a5fa" transparent opacity={0.3} />
      </mesh>
    </group>
  );
};

interface OrbitSpinnerProps {
  size?: number;
  className?: string;
}

const OrbitSpinner: React.FC<OrbitSpinnerProps> = ({ size = 200, className }) => {
  return (
    <div
      className={className}
      style={{
        width: size,
        height: size,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      <Canvas
        camera={{ position: [0, 0, 4], fov: 50 }}
        style={{ background: 'transparent' }}
      >
        <ambientLight intensity={0.5} />
        <WireframeSphere speed={0.8} />
      </Canvas>
    </div>
  );
};

export default OrbitSpinner;
