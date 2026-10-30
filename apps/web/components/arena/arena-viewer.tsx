"use client";

import { OrbitControls } from "@react-three/drei";
import { Canvas, useThree } from "@react-three/fiber";
import { Suspense, useLayoutEffect, useRef, type ReactNode } from "react";
import * as THREE from "three";
import type { OrbitControls as OrbitControlsImpl } from "three-stdlib";

import { Layer, type PartLayer } from "@/components/part-viewer/part-viewer";

export type Marker = { location: [number, number, number]; name: string };

/** Validator frame (mm, Z up) to the GLB frame (m, Y up): build123d writes a -90 degree X rotation. */
const TO_GLB = new THREE.Matrix4().makeRotationX(-Math.PI / 2).multiply(new THREE.Matrix4().makeScale(0.001, 0.001, 0.001));
const FOCUS_RADIUS = 0.03; // frame 30 mm around a focused check
const VIEW_DIR = new THREE.Vector3(1, 0.9, 1.2).normalize();

/** Frames the whole part, or one failed check, along a fixed iso direction. Re-runs on resize. */
function Framer({ content, focusAt, children }: { content: React.RefObject<THREE.Group | null>; focusAt: THREE.Vector3 | null; children?: ReactNode }) {
  const get = useThree((s) => s.get);
  const controlsReady = useThree((s) => !!s.controls);
  const size = useThree((s) => s.size);

  useLayoutEffect(() => {
    const group = content.current;
    if (!group) return;
    const camera = get().camera as THREE.PerspectiveCamera;
    const controls = get().controls as OrbitControlsImpl | null;
    const sphere = new THREE.Sphere();
    if (focusAt) sphere.set(focusAt, FOCUS_RADIUS);
    else new THREE.Box3().setFromObject(group).getBoundingSphere(sphere);
    if (!Number.isFinite(sphere.radius) || sphere.radius <= 0) return;

    const vFov = THREE.MathUtils.degToRad(camera.fov);
    const hFov = 2 * Math.atan(Math.tan(vFov / 2) * camera.aspect);
    const dist = (sphere.radius * 1.15) / Math.sin(Math.min(vFov, hFov) / 2);
    camera.position.copy(sphere.center).addScaledVector(VIEW_DIR, dist);
    camera.near = dist / 100;
    camera.far = dist * 100;
    camera.updateProjectionMatrix();
    camera.lookAt(sphere.center);
    if (controls) {
      controls.target.copy(sphere.center);
      controls.update();
    }
  }, [get, controlsReady, size.width, size.height, focusAt, content]);

  return <>{children}</>;
}

function Scene({ layers, markers, focus }: { layers: PartLayer[]; markers: Marker[]; focus: number | null }) {
  const content = useRef<THREE.Group>(null);
  const f = focus != null ? markers[focus] : null;
  const focusAt = f ? new THREE.Vector3(...f.location).applyMatrix4(TO_GLB) : null;

  return (
    <>
      <group ref={content}>
        {layers.map((l) => (
          <Layer key={`${l.tone}-${l.url}`} {...l} />
        ))}
      </group>
      <group matrixAutoUpdate={false} matrix={TO_GLB}>
        {markers.map((m, i) => (
          <mesh key={`${m.name}-${i}`} position={m.location} renderOrder={3}>
            {focus === i ? <torusGeometry args={[5, 0.6, 12, 48]} /> : <sphereGeometry args={[2.6, 24, 16]} />}
            <meshBasicMaterial color="#c8261b" transparent opacity={focus === i ? 1 : 0.75} depthTest={false} />
          </mesh>
        ))}
      </group>
      <Framer content={content} focusAt={focusAt ? focusAt : null} key={focusAt ? focusAt.toArray().join() : "all"} />
    </>
  );
}

export default function ArenaViewer({
  layers,
  markers,
  focus,
  label,
}: {
  layers: PartLayer[];
  markers: Marker[];
  focus: number | null;
  label: string;
}) {
  return (
    <Canvas aria-label={label} role="img" dpr={[1, 2]} camera={{ fov: 32, near: 0.001, far: 100 }}>
      <ambientLight intensity={0.9} />
      <directionalLight position={[2, 4, 3]} intensity={1.6} />
      <directionalLight position={[-3, 1, -2]} intensity={0.5} />
      <Suspense fallback={null}>
        <Scene layers={layers} markers={markers} focus={focus} />
      </Suspense>
      {/* no wheel zoom: the page must keep scrolling over the canvas; failed checks zoom by click */}
      <OrbitControls makeDefault enablePan={false} enableZoom={false} />
    </Canvas>
  );
}
