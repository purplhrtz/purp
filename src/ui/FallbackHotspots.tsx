"use client";
import { useEffect, useState } from "react";
import * as THREE from "three";
import * as act from "@/state/actions";
import { BASE_ASPECT, HITS, INTRO } from "@/scene/shots";

/** Without WebGL the still stays up; these labelled markers sit over the same objects. */
export function FallbackHotspots() {
  const [pts, setPts] = useState<Record<string, { x: number; y: number }>>({});
  useEffect(() => {
    const place = () => {
      const w = innerWidth, h = innerHeight;
      const portrait = w / h < 0.85;
      const v = INTRO[portrait ? "portrait" : "landscape"];
      const base = BASE_ASPECT[portrait ? "portrait" : "landscape"];
      // reproduce object-fit: cover of the still
      const scale = Math.max(w / (base * 1000), h / 1000);
      const iw = base * 1000 * scale, ih = 1000 * scale;
      const cam = new THREE.PerspectiveCamera(v.fov, base, 0.05, 50);
      cam.position.set(...v.pos);
      cam.lookAt(new THREE.Vector3(...v.target));
      cam.updateMatrixWorld();
      const out: Record<string, { x: number; y: number }> = {};
      for (const k of ["laptop", "barry", "cork", "lamp", "monitorL"] as const) {
        const p = new THREE.Vector3(...HITS[k].center).project(cam);
        out[k] = { x: (w - iw) / 2 + (p.x * 0.5 + 0.5) * iw, y: (h - ih) / 2 + (-p.y * 0.5 + 0.5) * ih };
      }
      setPts(out);
    };
    place();
    addEventListener("resize", place);
    return () => removeEventListener("resize", place);
  }, []);
  const spot = (k: string, label: string, fn: () => void) =>
    pts[k] && (
      <div className="hotspot" style={{ left: pts[k].x, top: pts[k].y }} key={k}>
        <button className="chip" onClick={fn}>{label}</button>
      </div>
    );
  return (
    <>
      {spot("laptop", "Laptop", () => act.openLaptop("ctl-laptop"))}
      {spot("barry", "Barry", () => act.pokeBarry("ctl-barry"))}
      {spot("monitorL", "Monitors", act.toggleMonitors)}
    </>
  );
}
