"use client";
import { useMemo, useRef } from "react";
import * as THREE from "three";
import { useFrame } from "@react-three/fiber";
import { useStore } from "@/state/store";
import { LAMP } from "./shots";

/** Dust motes that only show where the lamp cone catches them. */
export function Dust({ count = 260, reducedMotion }: { count?: number; reducedMotion: boolean }) {
  const ref = useRef<THREE.Points>(null);
  const { geo, mat } = useMemo(() => {
    const g = new THREE.BufferGeometry();
    const p = new Float32Array(count * 3);
    const seed = new Float32Array(count);
    for (let i = 0; i < count; i++) {
      p[i * 3] = -0.5 + (Math.random() - 0.5) * 1.3;
      p[i * 3 + 1] = 0.78 + Math.random() * 0.55;
      p[i * 3 + 2] = -5.6 + (Math.random() - 0.5) * 0.9;
      seed[i] = Math.random();
    }
    g.setAttribute("position", new THREE.BufferAttribute(p, 3));
    g.setAttribute("seed", new THREE.BufferAttribute(seed, 1));
    const m = new THREE.ShaderMaterial({
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
      uniforms: {
        uTime: { value: 0 },
        uLamp: { value: 1 },
        uBulb: { value: new THREE.Vector3(...LAMP.bulb) },
        uDir: { value: new THREE.Vector3(...(LAMP.target as [number, number, number])).sub(new THREE.Vector3(...LAMP.bulb)).normalize() },
        uPx: { value: 1 },
      },
      vertexShader: `
        attribute float seed; uniform float uTime; uniform vec3 uBulb; uniform vec3 uDir; uniform float uLamp; uniform float uPx;
        varying float vA;
        void main(){
          vec3 p = position;
          float t = uTime * (0.02 + seed * 0.03);
          p.x += sin(t * 6.0 + seed * 40.0) * 0.06;
          p.y += mod(-t + seed, 1.0) * -0.25 + 0.12;
          p.z += cos(t * 5.0 + seed * 17.0) * 0.05;
          vec3 d = p - uBulb;
          float along = dot(d, uDir);
          float off = length(d - uDir * along);
          float cone = smoothstep(0.75, 0.35, off / max(along, 0.01)) * step(0.02, along);
          vA = cone * uLamp * (0.35 + 0.65 * fract(seed * 7.3)) * smoothstep(0.0, 0.15, along);
          vec4 mv = modelViewMatrix * vec4(p, 1.0);
          gl_Position = projectionMatrix * mv;
          gl_PointSize = uPx * (1.2 + seed * 2.2) * (1.0 / -mv.z);
        }`,
      fragmentShader: `
        varying float vA;
        void main(){
          vec2 c = gl_PointCoord - 0.5;
          float a = smoothstep(0.5, 0.0, length(c)) * vA;
          gl_FragColor = vec4(vec3(1.0, 0.78, 0.55) * a * 0.9, a);
        }`,
    });
    return { geo: g, mat: m };
  }, [count]);
  useFrame((state, dt) => {
    mat.uniforms.uTime.value += reducedMotion ? 0 : dt;
    const lamp = useStore.getState().lampOn ? 1 : 0;
    mat.uniforms.uLamp.value += (lamp - mat.uniforms.uLamp.value) * Math.min(1, dt * 6);
    mat.uniforms.uPx.value = state.gl.getPixelRatio() * 2.2;
  });
  return <points ref={ref} geometry={geo} material={mat} frustumCulled={false} />;
}
