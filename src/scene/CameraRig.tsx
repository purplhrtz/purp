"use client";
import { useEffect, useMemo, useRef } from "react";
import * as THREE from "three";
import { useFrame, useThree } from "@react-three/fiber";
import { useStore, type Shot } from "@/state/store";
import { BASE_ASPECT, INTRO, SCREEN, SHOTS, type ShotDef } from "./shots";

const DEG = Math.PI / 180;
const easeInOut = (t: number) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
const easeOutSoft = (t: number) => 1 - Math.pow(1 - t, 2.2);

type Pose = { pos: THREE.Vector3; target: THREE.Vector3; fov: number; roll: number };
const toPose = (d: ShotDef): Pose => ({ pos: new THREE.Vector3(...d.pos), target: new THREE.Vector3(...d.target), fov: d.fov, roll: d.roll ?? 0 });

/** Keep the art-directed crop: like CSS object-fit: cover against the still's aspect. */
function coverFov(fov: number, aspect: number, base: number) {
  if (aspect <= base) return fov;
  return 2 * Math.atan(Math.tan((fov * DEG) / 2) * (base / aspect)) / DEG;
}

export function CameraRig({ reducedMotion }: { reducedMotion: boolean }) {
  const camera = useThree((s) => s.camera) as THREE.PerspectiveCamera;
  const size = useThree((s) => s.size);
  const gl = useThree((s) => s.gl);
  const portrait = size.width / size.height < 0.85;
  const variant = portrait ? "portrait" : "landscape";
  const shot = useStore((s) => s.shot);
  const introDone = useStore((s) => s.introDone);

  const cur = useRef<Pose>(toPose(INTRO[variant]));
  const tween = useRef<{ from: Pose; to: Pose; t: number; dur: number; ease: (t: number) => number } | null>(null);
  const look = useRef({ yaw: 0, pitch: 0, tyaw: 0, tpitch: 0 });
  const drag = useRef<{ x: number; y: number; id: number; moved: boolean } | null>(null);
  const tmp = useMemo(() => ({ dir: new THREE.Vector3(), up: new THREE.Vector3(), m: new THREE.Matrix4(), q: new THREE.Quaternion(), e: new THREE.Euler(0, 0, 0, "YXZ"), v: new THREE.Vector3() }), []);

  const startTween = (to: Pose, dur: number, ease = easeInOut) => {
    const from = { pos: cur.current.pos.clone(), target: cur.current.target.clone(), fov: cur.current.fov, roll: cur.current.roll };
    tween.current = { from, to, t: 0, dur: reducedMotion ? 0 : dur, ease };
  };

  // opening push (skippable) — or straight to the settled frame for reduced motion
  const pushed = useRef(false);
  useEffect(() => {
    if (pushed.current) return;
    pushed.current = true;
    cur.current = toPose(INTRO[variant]);
    if (reducedMotion) {
      cur.current = toPose(SHOTS.overview[variant]);
      useStore.getState().set({ introDone: true });
      return;
    }
    const id = window.setTimeout(() => startTween(toPose(SHOTS.overview[variant]), 6.5, easeOutSoft), 450);
    const done = window.setTimeout(() => useStore.getState().set({ introDone: true }), 7200);
    return () => {
      window.clearTimeout(id);
      window.clearTimeout(done);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // shot changes (and skipping the intro) — steady, decisive moves
  const lastShot = useRef<Shot>("overview");
  const lastVariant = useRef(variant);
  useEffect(() => {
    const changed = shot !== lastShot.current || variant !== lastVariant.current;
    lastShot.current = shot;
    lastVariant.current = variant;
    if (!changed && !introDone) return;
    const to = toPose(SHOTS[shot][variant]);
    const dist = to.pos.distanceTo(cur.current.pos);
    startTween(to, Math.min(2.4, 1.1 + dist * 0.28));
    look.current.tyaw = 0;
    look.current.tpitch = 0;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [shot, variant, introDone]);

  // drag to look (mouse or finger) on the canvas only; taps fall through to object clicks
  useEffect(() => {
    const el = gl.domElement;
    const lim = () => SHOTS[useStore.getState().shot][variant].look;
    const down = (e: PointerEvent) => {
      drag.current = { x: e.clientX, y: e.clientY, id: e.pointerId, moved: false };
      if (!useStore.getState().introDone) useStore.getState().set({ introDone: true });
    };
    const move = (e: PointerEvent) => {
      const d = drag.current;
      if (!d || d.id !== e.pointerId) return;
      const dx = e.clientX - d.x, dy = e.clientY - d.y;
      if (!d.moved && Math.hypot(dx, dy) < 8) return;
      if (!d.moved) {
        d.moved = true;
        try {
          el.setPointerCapture(e.pointerId);
        } catch {}
      }
      d.x = e.clientX;
      d.y = e.clientY;
      const [my, mp] = lim();
      const k = 0.16 * (size.width < 700 ? 1.5 : 1);
      look.current.tyaw = THREE.MathUtils.clamp(look.current.tyaw + dx * k, -my, my);
      look.current.tpitch = THREE.MathUtils.clamp(look.current.tpitch + dy * k, -mp, mp);
    };
    const up = (e: PointerEvent) => {
      if (drag.current?.id === e.pointerId) drag.current = null;
    };
    const key = (e: KeyboardEvent) => {
      if (document.activeElement !== el.parentElement && document.activeElement !== el) return;
      const [my, mp] = lim();
      const step = 6;
      if (e.key === "ArrowLeft") look.current.tyaw = Math.max(-my, look.current.tyaw - step);
      else if (e.key === "ArrowRight") look.current.tyaw = Math.min(my, look.current.tyaw + step);
      else if (e.key === "ArrowUp") look.current.tpitch = Math.max(-mp, look.current.tpitch - step);
      else if (e.key === "ArrowDown") look.current.tpitch = Math.min(mp, look.current.tpitch + step);
      else return;
      e.preventDefault();
    };
    el.addEventListener("pointerdown", down);
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
    window.addEventListener("pointercancel", up);
    window.addEventListener("keydown", key);
    return () => {
      el.removeEventListener("pointerdown", down);
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
      window.removeEventListener("pointercancel", up);
      window.removeEventListener("keydown", key);
    };
  }, [gl, variant, size.width]);

  const corners = useMemo(() => {
    // laptop display corners, from the Blender lid transform (tilted back 14deg)
    const c = new THREE.Vector3(...SCREEN.center);
    const right = new THREE.Vector3(1, 0, 0).multiplyScalar(SCREEN.w / 2);
    const upv = new THREE.Vector3(0, Math.cos(SCREEN.tiltDeg * DEG), -Math.sin(SCREEN.tiltDeg * DEG)).multiplyScalar(SCREEN.h / 2);
    return [c.clone().sub(right).add(upv), c.clone().add(right).add(upv), c.clone().add(right).sub(upv), c.clone().sub(right).sub(upv)];
  }, []);
  const rectKey = useRef("");

  useFrame((_, dt) => {
    const tw = tween.current;
    if (tw) {
      tw.t = tw.dur <= 0 ? 1 : Math.min(1, tw.t + dt / tw.dur);
      const k = tw.ease(tw.t);
      cur.current.pos.lerpVectors(tw.from.pos, tw.to.pos, k);
      cur.current.target.lerpVectors(tw.from.target, tw.to.target, k);
      cur.current.fov = THREE.MathUtils.lerp(tw.from.fov, tw.to.fov, k);
      cur.current.roll = THREE.MathUtils.lerp(tw.from.roll, tw.to.roll, k);
      if (tw.t >= 1) tween.current = null;
    }
    // look offsets ease in, and drift back home when you let go in close-ups
    const L = look.current;
    const kk = reducedMotion ? 1 : 1 - Math.exp(-8 * dt);
    L.yaw += (L.tyaw - L.yaw) * kk;
    L.pitch += (L.tpitch - L.pitch) * kk;

    const p = cur.current;
    camera.position.copy(p.pos);
    tmp.m.lookAt(p.pos, p.target, new THREE.Vector3(0, 1, 0));
    camera.quaternion.setFromRotationMatrix(tmp.m);
    tmp.e.set(-L.pitch * DEG, -L.yaw * DEG, p.roll * DEG, "YXZ");
    camera.quaternion.multiply(tmp.q.setFromEuler(tmp.e));
    const base = BASE_ASPECT[variant];
    const fov = coverFov(p.fov, size.width / size.height, base);
    if (Math.abs(camera.fov - fov) > 1e-4) {
      camera.fov = fov;
      camera.updateProjectionMatrix();
    }

    // where is the laptop display on screen? the HTML storefront docks onto it
    const st = useStore.getState();
    if (st.shot === "desk" && !tween.current) {
      camera.updateMatrixWorld();
      let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
      for (const c of corners) {
        tmp.v.copy(c).project(camera);
        const x = (tmp.v.x * 0.5 + 0.5) * size.width;
        const y = (-tmp.v.y * 0.5 + 0.5) * size.height;
        x0 = Math.min(x0, x); x1 = Math.max(x1, x); y0 = Math.min(y0, y); y1 = Math.max(y1, y);
      }
      const r = { x: Math.round(x0), y: Math.round(y0), w: Math.round(x1 - x0), h: Math.round(y1 - y0) };
      const key = `${r.x},${r.y},${r.w},${r.h}`;
      if (key !== rectKey.current && Math.abs(L.yaw - L.tyaw) < 0.05) {
        rectKey.current = key;
        st.set({ screenRect: r });
      }
    } else if (rectKey.current) {
      rectKey.current = "";
      st.set({ screenRect: null });
    }
  });

  return null;
}
