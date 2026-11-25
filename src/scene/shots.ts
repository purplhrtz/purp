import type { Shot } from "@/state/store";

/** Blender (x, y, z; Z-up) -> three.js (x, z, -y) */
export const b2t = ([x, y, z]: [number, number, number]): [number, number, number] => [x, z, -y];

export type ShotDef = {
  pos: [number, number, number];
  target: [number, number, number];
  fov: number; // vertical, at the base aspect
  roll?: number; // degrees
  look: [number, number]; // max yaw/pitch offset for drag-to-look (degrees)
};
type Variant = { landscape: ShotDef; portrait: ShotDef };

// The opening frame — identical to the Blender camera that renders /stills/overview*.jpg
export const INTRO: Variant = {
  landscape: { pos: b2t([2.04, 0.56, 1.55]), target: b2t([-0.1, 5.6, 0.84]), fov: 38, look: [40, 15] },
  portrait: { pos: b2t([1.92, 0.6, 1.45]), target: b2t([0.58, 5.6, 0.95]), fov: 60, look: [30, 15] },
};
export const BASE_ASPECT = { landscape: 16 / 9, portrait: 1080 / 2340 };

export const SHOTS: Record<Shot, Variant> = {
  // where the opening push settles: a step off the stairs, desk and Barry both in frame
  overview: {
    landscape: { pos: b2t([1.62, 1.35, 1.48]), target: b2t([-0.05, 5.6, 0.82]), fov: 38, look: [42, 16] },
    portrait: { pos: b2t([1.55, 1.55, 1.38]), target: b2t([0.55, 5.6, 0.9]), fov: 66, look: [32, 16] },
  },
  desk: {
    landscape: { pos: [-0.27, 0.975, -5.439], target: [-0.27, 0.873, -5.846], fov: 38, look: [10, 6] },
    portrait: { pos: [-0.3, 1.12, -5.05], target: [-0.45, 0.83, -5.75], fov: 66, look: [12, 8] },
  },
  couch: {
    landscape: { pos: b2t([-1.95, 2.7, 1.02]), target: b2t([0.3, 5.4, 0.78]), fov: 46, look: [38, 12] },
    portrait: { pos: b2t([-1.95, 2.7, 1.02]), target: b2t([0.55, 5.35, 0.72]), fov: 76, look: [30, 12] },
  },
  cork: {
    landscape: { pos: b2t([-1.62, 4.5, 1.5]), target: b2t([-2.58, 4.9, 1.38]), fov: 40, roll: -3, look: [12, 8] },
    portrait: { pos: b2t([-1.35, 4.88, 1.42]), target: b2t([-2.58, 4.88, 1.38]), fov: 74, roll: -2, look: [10, 8] },
  },
  barry: {
    landscape: { pos: b2t([0.8, 4.72, 0.9]), target: b2t([1.3, 5.58, 0.58]), fov: 32, look: [18, 10] },
    portrait: { pos: b2t([0.85, 4.75, 0.92]), target: b2t([1.3, 5.6, 0.58]), fov: 58, look: [16, 10] },
  },
};

/** Invisible hit volumes for tap targets (three.js coords): center, size */
export const HITS = {
  laptop: { center: [-0.27, 0.86, -5.75], size: [0.36, 0.26, 0.3] },
  barry: { center: [1.31, 0.6, -5.6], size: [0.52, 0.26, 0.52] },
  cork: { center: [-2.56, 1.4, -4.875], size: [0.12, 0.92, 1.22] },
  lamp: { center: [-0.49, 1.24, -5.66], size: [0.22, 0.2, 0.22] },
  lampBase: { center: [0.28, 0.8, -5.98], size: [0.18, 0.1, 0.18] },
  monitorL: { center: [-1.32, 1.12, -5.99], size: [0.24, 0.36, 0.28] },
  monitorR: { center: [0.52, 1.12, -5.99], size: [0.24, 0.36, 0.28] },
  couch: { center: [-2.15, 0.45, -2.75], size: [0.9, 0.8, 2.0] },
} as const;

export const LAMP = { bulb: [-0.492, 1.243, -5.656] as const, target: b2t([-0.66, 5.74, 0.76]), barry: b2t([1.31, 5.55, 0.6]) };
export const SCREEN = { center: [-0.27, 0.873, -5.846] as const, w: 0.284, h: 0.181, tiltDeg: 14 };
