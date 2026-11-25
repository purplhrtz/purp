"use client";
import { useEffect, useMemo, useRef } from "react";
import * as THREE from "three";
import { useFrame, useThree, type ThreeEvent } from "@react-three/fiber";
import { useGLTF, useTexture } from "@react-three/drei";
import { useStore } from "@/state/store";
import * as act from "@/state/actions";
import { audio } from "@/audio/engine";
import { HITS, LAMP } from "./shots";
import { makeLightmapUniforms, patchLightmapped, setGroup, type LightmapInfo } from "./lightmap";
import { createScreen } from "./screenCanvas";

const damp = (a: number, b: number, k: number, dt: number) => a + (b - a) * (1 - Math.exp(-k * dt));

export function Room({ info, lowTier }: { info: LightmapInfo; lowTier: boolean }) {
  const { scene } = useGLTF("/models/studio.glb");
  const [lmRGB, lmAmb] = useTexture(
    lowTier ? ["/models/lightmap-rgb-1k.webp", "/models/lightmap-amb-1k.webp"] : ["/models/lightmap-rgb.webp", "/models/lightmap-amb.webp"],
  );
  const gl = useThree((s) => s.gl);
  const threeScene = useThree((s) => s.scene);
  const uniforms = useMemo(() => {
    for (const t of [lmRGB, lmAmb]) {
      t.flipY = false; // glTF UV convention
      t.colorSpace = THREE.NoColorSpace;
      t.generateMipmaps = true;
      t.minFilter = THREE.LinearMipmapLinearFilter;
      t.needsUpdate = true;
    }
    return makeLightmapUniforms(lmRGB, lmAmb);
  }, [lmRGB, lmAmb]);
  const screen = useMemo(() => createScreen(), []);
  const refs = useRef<{ bulb?: THREE.MeshStandardMaterial; strip?: THREE.MeshStandardMaterial; screen?: THREE.MeshBasicMaterial; leds: THREE.MeshStandardMaterial[]; statics: THREE.MeshStandardMaterial[] }>({ leds: [], statics: [] });

  useEffect(() => {
    const r = refs.current;
    r.leds = [];
    r.statics = [];
    scene.traverse((o) => {
      const m = o as THREE.Mesh;
      if (!m.isMesh) return;
      const name = (m.name || "") + " " + (m.parent?.name || "");
      const mat = m.material as THREE.MeshStandardMaterial;
      if (/Room_Static/.test(name)) {
        patchLightmapped(mat, uniforms);
        mat.envMapIntensity = 0.55;
        r.statics.push(mat);
        m.matrixAutoUpdate = false;
        m.updateMatrix();
      } else if (/Laptop_Screen/.test(name)) {
        const sm = new THREE.MeshBasicMaterial({ map: screen.tex, toneMapped: false, color: new THREE.Color(0, 0, 0) });
        m.material = sm;
        r.screen = sm;
      } else if (/Lamp_Bulb/.test(name)) {
        r.bulb = mat;
      } else if (/violet_strip/.test(name)) {
        r.strip = mat;
      } else if (/led/i.test(name)) {
        r.leds.push(mat);
      }
    });
  }, [scene, uniforms, screen]);

  // Reflections: capture the lit room once (and again when the lamp changes).
  const lampOn = useStore((s) => s.lampOn);
  useEffect(() => {
    const rt = new THREE.WebGLCubeRenderTarget(lowTier ? 64 : 128, { type: THREE.HalfFloatType });
    const cam = new THREE.CubeCamera(0.05, 20, rt);
    cam.position.set(-0.2, 1.1, -4.9);
    const pmrem = new THREE.PMREMGenerator(gl);
    let env: THREE.Texture | null = null;
    const id = window.setTimeout(() => {
      cam.update(gl, threeScene);
      env = pmrem.fromCubemap(rt.texture).texture;
      threeScene.environment = env;
    }, 900);
    return () => {
      window.clearTimeout(id);
      rt.dispose();
      pmrem.dispose();
      env?.dispose();
    };
  }, [gl, threeScene, lampOn, lowTier]);

  const lights = useRef<{ lamp: THREE.SpotLight | null; fill: THREE.SpotLight | null; violet: THREE.PointLight | null; screen: THREE.PointLight | null; hemi: THREE.HemisphereLight | null }>({ lamp: null, fill: null, violet: null, screen: null, hemi: null });
  const w = useRef({ lamp: 1, violet: 1, screen: 0, wake: 0 });
  const lampTarget = useMemo(() => {
    const o = new THREE.Object3D();
    o.position.set(...(LAMP.target as [number, number, number]));
    return o;
  }, []);
  const barryTarget = useMemo(() => {
    const o = new THREE.Object3D();
    o.position.set(...(LAMP.barry as [number, number, number]));
    return o;
  }, []);

  useFrame((state, dt) => {
    const st = useStore.getState();
    const W = w.current;
    const level = audio.musicLevel();
    W.lamp = damp(W.lamp, st.lampOn ? 1 : 0, st.lampOn ? 9 : 14, dt);
    const violetMood = 1 - W.lamp;
    // the violet strip breathes gently with the music — restrained, the room should still look photographed
    const breathe = 1 + level * 0.3 + (st.playing ? Math.sin(state.clock.elapsedTime * 1.3) * 0.04 : 0);
    W.violet = damp(W.violet, (1 + violetMood * 0.9) * breathe, 6, dt);
    W.wake = damp(W.wake, st.laptopAwake ? 1 : 0, st.laptopAwake ? 2.2 : 4, dt);
    const u = uniforms;
    setGroup(u.lmLamp.value, info, "lamp", W.lamp);
    setGroup(u.lmViolet.value, info, "violet", W.violet);
    setGroup(u.lmScreen.value, info, "screen", 0.03 + W.wake * (1.0 + 0.6 * violetMood));
    setGroup(u.lmAmbient.value, info, "ambient", 1.0 + violetMood * 0.4);
    u.lmLift.value = 0.0018 + violetMood * 0.0012; // keeps the room legible on phones
    const r = refs.current;
    if (r.bulb) r.bulb.emissiveIntensity = 0.05 + W.lamp * 60;
    if (r.strip) r.strip.emissiveIntensity = 6 * W.violet;
    if (r.screen) r.screen.color.setScalar(0.06 + W.wake * 0.94);
    for (const m of r.statics) m.envMapIntensity = 0.3 + W.lamp * 0.35;
    const L = lights.current;
    if (L.lamp) L.lamp.intensity = W.lamp * 3.2;
    if (L.fill) L.fill.intensity = W.lamp * 3.6;
    if (L.violet) L.violet.intensity = 0.5 * W.violet;
    if (L.screen) L.screen.intensity = W.wake * 0.35;
    if (L.hemi) L.hemi.intensity = 0.12 + violetMood * 0.12;
    screen.draw(st.laptopAwake, st.tab, st.cart.length);
  });

  const tap = (fn: () => void) => (e: ThreeEvent<MouseEvent>) => {
    e.stopPropagation();
    if (e.delta > 8) return; // it was a drag, not a tap
    fn();
  };
  const hover = {
    onPointerOver: (e: ThreeEvent<PointerEvent>) => {
      e.stopPropagation();
      document.body.style.cursor = "pointer";
    },
    onPointerOut: () => {
      document.body.style.cursor = "";
    },
  };
  const hit = (key: keyof typeof HITS, fn: () => void, label: string) => {
    const h = HITS[key];
    return (
      <mesh key={key} name={`hit:${label}`} position={h.center as unknown as [number, number, number]} onClick={tap(fn)} {...hover}>
        <boxGeometry args={h.size as unknown as [number, number, number]} />
        <meshBasicMaterial visible={false} />
      </mesh>
    );
  };

  return (
    <group>
      <primitive object={scene} />
      <primitive object={lampTarget} />
      <primitive object={barryTarget} />
      <spotLight ref={(l) => { lights.current.lamp = l; }} position={LAMP.bulb as unknown as [number, number, number]} target={lampTarget}
        angle={0.8} penumbra={0.8} decay={2} distance={4} color="#ffb070" />
      <spotLight ref={(l) => { lights.current.fill = l; }} position={LAMP.bulb as unknown as [number, number, number]} target={barryTarget}
        angle={0.24} penumbra={1} decay={2} distance={4} color="#ffb070" />
      <pointLight ref={(l) => { lights.current.violet = l; }} position={[-0.35, 1.05, -6.0]} distance={3.5} decay={2} color="#7a3cff" />
      <pointLight ref={(l) => { lights.current.screen = l; }} position={[-0.27, 0.95, -5.65]} distance={1.4} decay={2} color="#b8c0ff" />
      <hemisphereLight ref={(l) => { lights.current.hemi = l; }} args={["#4a3a5e", "#2a1810", 0.15]} />
      {hit("laptop", () => act.openLaptop("ctl-laptop"), "laptop")}
      {hit("barry", () => act.pokeBarry("ctl-barry"), "barry")}
      {hit("cork", () => act.go("cork", "ctl-cork"), "corkboard")}
      {hit("lamp", act.toggleLamp, "lamp")}
      {hit("lampBase", act.toggleLamp, "lamp base")}
      {hit("monitorL", act.toggleMonitors, "left monitor")}
      {hit("monitorR", act.toggleMonitors, "right monitor")}
      {hit("couch", () => act.go("couch", "ctl-couch"), "couch")}
    </group>
  );
}

useGLTF.preload("/models/studio.glb");
