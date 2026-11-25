"use client";
import { Suspense, useEffect, useState } from "react";
import * as THREE from "three";
import { Canvas, useThree } from "@react-three/fiber";
import { AdaptiveDpr, PerformanceMonitor } from "@react-three/drei";
import { useStore } from "@/state/store";
import { Room } from "./Room";
import { Barry } from "./Barry";
import { CameraRig } from "./CameraRig";
import { Dust } from "./Dust";
import { Effects } from "./Effects";
import type { LightmapInfo } from "./lightmap";

export type Tier = "low" | "mid" | "high";

export function detectTier(): Tier {
  if (typeof window === "undefined") return "mid";
  const mobile = matchMedia("(pointer: coarse)").matches || window.innerWidth < 760;
  const mem = (navigator as unknown as { deviceMemory?: number }).deviceMemory ?? 8;
  const cores = navigator.hardwareConcurrency ?? 4;
  if (mobile && (mem <= 4 || cores <= 4)) return "low";
  if (mobile) return "mid";
  return mem >= 8 && cores >= 8 ? "high" : "mid";
}

function Ready() {
  const gl = useThree((s) => s.gl);
  useEffect(() => {
    // first real frame drawn: let the UI cross-fade from the still
    let raf = requestAnimationFrame(() => {
      raf = requestAnimationFrame(() => useStore.getState().set({ sceneReady: true }));
    });
    return () => cancelAnimationFrame(raf);
  }, [gl]);
  return null;
}

export default function Studio({ reducedMotion }: { reducedMotion: boolean }) {
  const [info, setInfo] = useState<LightmapInfo | null>(null);
  const [tier, setTier] = useState<Tier>("mid");
  useEffect(() => {
    setTier(detectTier());
    fetch("/models/lightmap.json")
      .then((r) => r.json())
      .then(setInfo)
      .catch(() => useStore.getState().set({ webgl: "no" }));
  }, []);
  if (!info) return null;
  const dprMax = tier === "high" ? 2 : tier === "mid" ? 1.6 : 1.25;
  return (
    <Canvas
      dpr={[1, dprMax]}
      gl={{ antialias: tier !== "low", powerPreference: "high-performance", alpha: false, stencil: false }}
      camera={{ fov: 38, near: 0.03, far: 30, position: [2, 1.5, -0.4] }}
      onCreated={({ gl }) => {
        gl.toneMapping = THREE.AgXToneMapping;
        gl.toneMappingExposure = 3.1;
        gl.outputColorSpace = THREE.SRGBColorSpace;
        gl.setClearColor("#050407");
      }}
      aria-hidden
    >
      <PerformanceMonitor onDecline={() => setTier((t) => (t === "high" ? "mid" : "low"))} flipflops={2} />
      <AdaptiveDpr pixelated={false} />
      <CameraRig reducedMotion={reducedMotion} />
      <Suspense fallback={null}>
        <Room info={info} lowTier={tier === "low"} />
        <Barry lowTier={tier === "low"} reducedMotion={reducedMotion} />
        {tier !== "low" && <Dust reducedMotion={reducedMotion} count={tier === "high" ? 320 : 160} />}
        <Effects tier={tier} />
        <Ready />
      </Suspense>
    </Canvas>
  );
}
