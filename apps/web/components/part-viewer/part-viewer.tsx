"use client";

import { Bounds, Edges, OrbitControls, useGLTF } from "@react-three/drei";
import { Canvas } from "@react-three/fiber";
import { Suspense, useMemo, useSyncExternalStore } from "react";
import * as THREE from "three";

export type PartLayer = {
  /** GLB exported by build123d (validator-side): /public assets or the read API */
  url: string;
  tone: "part" | "fail" | "ghost";
};

const TONES = {
  part: { color: "#d8d8d4", edges: "#262626", emissive: "#000000" },
  fail: { color: "#c8261b", edges: "#7a160f", emissive: "#5a0d07" },
  ghost: { color: "#ff5e1f", edges: "#ff5e1f", emissive: "#000000" },
} as const;

function subscribeReducedMotion(onChange: () => void) {
  const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
  mq.addEventListener("change", onChange);
  return () => mq.removeEventListener("change", onChange);
}

function useReducedMotion() {
  return useSyncExternalStore(
    subscribeReducedMotion,
    () => window.matchMedia("(prefers-reduced-motion: reduce)").matches,
    () => true,
  );
}

/** Bakes every mesh of the GLB into world space so edges and materials can be set per layer. */
export function Layer({ url, tone }: PartLayer) {
  const { scene } = useGLTF(url);
  const geometries = useMemo(() => {
    const out: THREE.BufferGeometry[] = [];
    scene.updateMatrixWorld(true);
    scene.traverse((obj) => {
      const mesh = obj as THREE.Mesh;
      if (mesh.isMesh) out.push(mesh.geometry.clone().applyMatrix4(mesh.matrixWorld));
    });
    return out;
  }, [scene]);
  const t = TONES[tone];

  return (
    <>
      {geometries.map((g, i) =>
        tone === "ghost" ? (
          // reference overlay: edges only plus a faint fill, so missing or extra geometry shows through
          <mesh key={i} geometry={g} renderOrder={2}>
            <meshBasicMaterial color={t.color} transparent opacity={0.07} depthWrite={false} />
            <Edges threshold={25} color={t.edges} />
          </mesh>
        ) : (
          <mesh key={i} geometry={g}>
            <meshStandardMaterial
              color={t.color}
              emissive={t.emissive}
              metalness={0.15}
              roughness={0.55}
              polygonOffset
              polygonOffsetFactor={1}
            />
            <Edges threshold={25} color={t.edges} />
          </mesh>
        ),
      )}
    </>
  );
}

export default function PartViewer({ layers, label }: { layers: PartLayer[]; label: string }) {
  const still = useReducedMotion();

  return (
    <Canvas
      aria-label={label}
      role="img"
      dpr={[1, 2]}
      frameloop={still ? "demand" : "always"}
      camera={{ position: [1, 0.85, 1.15], fov: 32, near: 0.001, far: 100 }}
    >
      <ambientLight intensity={0.9} />
      <directionalLight position={[2, 4, 3]} intensity={1.6} />
      <directionalLight position={[-3, 1, -2]} intensity={0.5} />
      <Suspense fallback={null}>
        <Bounds fit clip observe margin={1.15}>
          {layers.map((l) => (
            <Layer key={l.url} {...l} />
          ))}
        </Bounds>
      </Suspense>
      <OrbitControls makeDefault enableZoom={false} enablePan={false} autoRotate={!still} autoRotateSpeed={0.9} />
    </Canvas>
  );
}
