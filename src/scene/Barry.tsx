"use client";
import { useEffect, useMemo, useRef } from "react";
import * as THREE from "three";
import { useFrame } from "@react-three/fiber";
import { useGLTF } from "@react-three/drei";
import { useStore } from "@/state/store";
import { audio } from "@/audio/engine";

type Reaction = "lift" | "blink" | "stretch" | "settle";
const REACTIONS: Reaction[] = ["lift", "blink", "stretch", "settle"];

const ease = (t: number) => (t <= 0 ? 0 : t >= 1 ? 1 : t * t * (3 - 2 * t));
const bump = (t: number, a: number, b: number, c: number, d: number) => ease((t - a) / (b - a)) * (1 - ease((t - c) / (d - c)));

/** Shell fur: extra copies of a mesh pushed out along the normal, cut out by a strand pattern. */
function furShells(src: THREE.Mesh, count: number, length: number) {
  const shells: THREE.Mesh[] = [];
  const base = src.material as THREE.MeshStandardMaterial;
  for (let i = 1; i <= count; i++) {
    const f = i / count;
    const mat = base.clone();
    mat.alphaTest = 0.5;
    mat.transparent = false;
    mat.onBeforeCompile = (shader) => {
      shader.uniforms.uShell = { value: f };
      shader.uniforms.uLen = { value: length };
      shader.vertexShader = shader.vertexShader
        .replace("#include <common>", "#include <common>\nuniform float uShell; uniform float uLen; varying vec3 vFurPos;")
        .replace("#include <begin_vertex>", "#include <begin_vertex>\ntransformed += normal * uShell * uLen;\nvFurPos = position;");
      shader.fragmentShader = shader.fragmentShader
        .replace("#include <common>", "#include <common>\nuniform float uShell; varying vec3 vFurPos;\nfloat furHash(vec3 p){ p = fract(p*0.3183099+.1); p*=17.0; return fract(p.x*p.y*p.z*(p.x+p.y+p.z)); }")
        .replace(
          "#include <alphatest_fragment>",
          `float strand = furHash(floor(vFurPos * 1400.0));
diffuseColor.a = step(uShell * uShell, strand * 0.92);
diffuseColor.rgb *= mix(0.55, 1.08, uShell);
#include <alphatest_fragment>`,
        );
    };
    mat.customProgramCacheKey = () => `fur-${i}`;
    const m = new THREE.Mesh(src.geometry, mat);
    m.name = `${src.name}_fur${i}`;
    m.raycast = () => {};
    shells.push(m);
  }
  return shells;
}

export function Barry({ lowTier, reducedMotion }: { lowTier: boolean; reducedMotion: boolean }) {
  const { scene } = useGLTF("/models/barry.glb");
  const parts = useRef<Record<string, THREE.Object3D | undefined>>({});
  const rest = useRef<Record<string, { p: THREE.Vector3; q: THREE.Quaternion; s: THREE.Vector3 }>>({});
  const st = useRef({ reaction: null as Reaction | null, t0: 0, lastReaction: "" as string, nextTwitch: 3, twitchEar: 0, twitchT: -10, lastPurr: -999, blinkT: -10, nextBlink: 6 });
  const tmp = useMemo(() => ({ v: new THREE.Vector3(), q: new THREE.Quaternion(), q2: new THREE.Quaternion(), m: new THREE.Matrix4() }), []);

  useEffect(() => {
    const p: Record<string, THREE.Object3D> = {};
    scene.traverse((o) => {
      p[o.name] = o;
      rest.current[o.name] = { p: o.position.clone(), q: o.quaternion.clone(), s: o.scale.clone() };
      const m = o as THREE.Mesh;
      if (m.isMesh) {
        const mat = m.material as THREE.MeshStandardMaterial;
        mat.envMapIntensity = 0.6;
        if (/Body|Head|Tail/.test(o.name)) {
          mat.roughness = 0.9;
        }
      }
    });
    // fur on the big masses
    for (const n of ["Barry_Body", "Barry_Head", "Barry_Tail"]) {
      const m = p[n] as THREE.Mesh | undefined;
      if (m?.isMesh && !m.userData.fur) {
        m.userData.fur = true;
        furShells(m, lowTier ? 4 : 9, n === "Barry_Tail" ? 0.006 : 0.009).forEach((s) => m.add(s));
      }
    }
    parts.current = p;
  }, [scene, lowTier]);

  const poke = useStore((s) => s.barryPoke);
  useEffect(() => {
    if (!poke) return;
    const s = st.current;
    const options = REACTIONS.filter((r) => r !== s.lastReaction);
    const r = options[Math.floor(Math.random() * options.length)];
    s.reaction = r;
    s.lastReaction = r;
    s.t0 = performance.now() / 1000;
    // purr sparingly: only some reactions, at most every 25s, and not always
    const now = s.t0;
    if ((r === "lift" || r === "settle" || r === "blink") && now - s.lastPurr > 25 && Math.random() < 0.45) {
      s.lastPurr = now;
      window.setTimeout(() => void audio.sfx(Math.random() < 0.5 ? "purr1" : "purr2", { gain: 0.55 }), 900);
    }
  }, [poke]);

  useFrame((state) => {
    const P = parts.current;
    const R = rest.current;
    if (!P.Barry_Body || !R.Barry_Body) return;
    const t = state.clock.elapsedTime;
    const now = performance.now() / 1000;
    const s = st.current;
    const focused = useStore.getState().shot === "barry";
    const rt = s.reaction ? now - s.t0 : 99;
    const dur = { lift: 7, blink: 5, stretch: 6, settle: 6 } as const;
    if (s.reaction && rt > dur[s.reaction] && !focused) s.reaction = null;
    const motion = reducedMotion ? 0.35 : 1;

    // breathing — slower, deeper when settling
    const br = Math.sin(t * ((Math.PI * 2) / (s.reaction === "settle" ? 4.2 : 3.1)));
    const body = P.Barry_Body;
    const stretch = s.reaction === "stretch" ? bump(rt, 0.6, 2.0, 3.4, 5.0) : 0;
    body.scale.set(R.Barry_Body.s.x * (1 + 0.012 * br + 0.09 * stretch), R.Barry_Body.s.y * (1 + 0.024 * br * motion - 0.05 * stretch), R.Barry_Body.s.z * (1 + 0.012 * br));

    // head
    const head = P.Barry_Head;
    if (head && R.Barry_Head) {
      let lift = 0;
      if (s.reaction === "lift") lift = focused ? ease(rt / 1.4) : bump(rt, 0, 1.4, 5, 7);
      if (s.reaction === "blink") lift = (focused ? ease(rt / 1.6) : bump(rt, 0, 1.6, 3.5, 5)) * 0.45;
      if (s.reaction === "stretch") lift = bump(rt, 0.4, 1.8, 3.6, 5.2) * 0.6;
      if (s.reaction === "settle") lift = bump(rt, 0, 0.8, 1.2, 3.0) * 0.3;
      lift *= motion;
      // look toward the camera: rotate local +X (his nose) toward the viewer
      const parent = head.parent!;
      tmp.v.copy(state.camera.position);
      parent.worldToLocal(tmp.v);
      tmp.v.sub(R.Barry_Head.p).normalize();
      tmp.q.setFromUnitVectors(new THREE.Vector3(1, 0, 0), tmp.v);
      tmp.q2.copy(R.Barry_Head.q).slerp(tmp.q, lift * 0.75);
      // tiny idle nod
      const nod = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 0, 1), Math.sin(t * 0.7) * 0.015 * motion + br * 0.01);
      head.quaternion.copy(tmp.q2).multiply(nod);
      head.position.copy(R.Barry_Head.p);
      head.position.y += lift * 0.035;
      head.position.x -= stretch * 0.012;
    }

    // eyes: closed while asleep; open on approach; slow blinks while looking
    const eyeOpen = (() => {
      if (!s.reaction) return 0;
      let o = 0;
      if (s.reaction === "lift") o = focused ? ease((rt - 0.6) / 0.8) : bump(rt, 0.6, 1.4, 4.6, 5.6);
      if (s.reaction === "blink") o = (focused ? ease((rt - 0.5) / 0.8) : bump(rt, 0.5, 1.3, 3.4, 4.4)) * 0.6;
      if (s.reaction === "stretch") o = bump(rt, 1.0, 1.6, 3.0, 3.6) * 0.5;
      if (s.reaction === "settle") o = bump(rt, 0.2, 0.6, 1.0, 2.2) * 0.4;
      // slow blink cycle while looking at you
      if (o > 0.3) {
        if (now > s.nextBlink) {
          s.blinkT = now;
          s.nextBlink = now + 3 + Math.random() * 4;
        }
        const b = now - s.blinkT;
        if (b < 1.4) o *= 1 - Math.sin((b / 1.4) * Math.PI) * 0.92;
      }
      return o;
    })();
    for (const n of ["Barry_EyeL", "Barry_EyeR"]) {
      const e = P[n];
      // Blender local Z (the lid axis) is local Y after glTF's Y-up conversion
      if (e && R[n]) e.scale.set(R[n].s.x, 0.12 + 0.88 * eyeOpen, R[n].s.z);
    }

    // ears: idle flicks; perk up when he's looking
    if (now > s.nextTwitch) {
      s.twitchEar = Math.random() < 0.5 ? 0 : 1;
      s.twitchT = now;
      s.nextTwitch = now + 3.5 + Math.random() * 6;
    }
    ["Barry_EarL", "Barry_EarR"].forEach((n, i) => {
      const e = P[n];
      if (!e || !R[n]) return;
      const tw = i === s.twitchEar ? bump(now - s.twitchT, 0, 0.08, 0.16, 0.35) : 0;
      const perk = eyeOpen * 0.25;
      e.quaternion.copy(R[n].q).multiply(tmp.q.setFromEuler(new THREE.Euler((i ? 1 : -1) * (tw * 0.35 + perk) * motion, 0, tw * 0.2 * motion)));
    });

    // tail tip sway
    const tail = P.Barry_Tail;
    if (tail && R.Barry_Tail) {
      tail.quaternion.copy(R.Barry_Tail.q).multiply(tmp.q.setFromAxisAngle(new THREE.Vector3(0, 1, 0), Math.sin(t * 0.45) * 0.025 * motion + (s.reaction === "stretch" ? bump(rt, 0.5, 1.5, 3, 4) * 0.06 : 0)));
    }
  });

  return <primitive object={scene} />;
}

useGLTF.preload("/models/barry.glb");
