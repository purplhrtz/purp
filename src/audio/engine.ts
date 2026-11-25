"use client";
/**
 * Tiny Web Audio engine. Nothing is created until the first user gesture (unlock), the master
 * gain gives instant mutes, room tone ducks under music, and each camera shot gets its own
 * "sound perspective" (filtering + level + pan) so moving through the room sounds like moving.
 */
import type { Shot } from "@/state/store";

type Perspective = { roomGain: number; roomLP: number; musicLP: number; musicGain: number; pan: number };
const PERSPECTIVE: Record<Shot, Perspective> = {
  overview: { roomGain: 0.55, roomLP: 900, musicLP: 4200, musicGain: 0.75, pan: -0.15 },
  desk: { roomGain: 0.35, roomLP: 1400, musicLP: 18000, musicGain: 1.0, pan: 0 },
  couch: { roomGain: 0.5, roomLP: 1100, musicLP: 7000, musicGain: 0.85, pan: 0.35 },
  cork: { roomGain: 0.6, roomLP: 700, musicLP: 3200, musicGain: 0.6, pan: 0.45 },
  barry: { roomGain: 0.4, roomLP: 1200, musicLP: 6000, musicGain: 0.8, pan: -0.35 },
};

const SFX = {
  click: "/media/sfx/lamp-click.mp3",
  startup: "/media/sfx/startup.mp3",
  purr1: "/media/sfx/purr-1.mp3",
  purr2: "/media/sfx/purr-2.mp3",
  tick: "/media/sfx/tick.mp3",
  room: "/media/sfx/room-tone.mp3",
} as const;
export type SfxName = keyof typeof SFX;

class Engine {
  ctx: AudioContext | null = null;
  master!: GainNode;
  roomGain!: GainNode;
  roomLP!: BiquadFilterNode;
  musicLP!: BiquadFilterNode;
  musicGain!: GainNode;
  musicVol!: GainNode;
  pan!: StereoPannerNode;
  analyser!: AnalyserNode;
  el: HTMLAudioElement | null = null;
  buffers = new Map<string, Promise<AudioBuffer | null>>();
  roomSrc: AudioBufferSourceNode | null = null;
  enabled = false;
  musicOn = false;
  shot: Shot = "overview";
  private data = new Uint8Array(256);
  private level = 0;

  /** Must be called from inside a user gesture. Safe to call repeatedly. */
  unlock() {
    if (typeof window === "undefined") return;
    if (!this.ctx) {
      const AC = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      if (!AC) return;
      const ctx = new AC();
      this.ctx = ctx;
      this.master = ctx.createGain();
      this.master.gain.value = 0;
      this.master.connect(ctx.destination);
      this.roomLP = ctx.createBiquadFilter();
      this.roomLP.type = "lowpass";
      this.roomGain = ctx.createGain();
      this.roomGain.gain.value = 0;
      this.roomLP.connect(this.roomGain).connect(this.master);
      this.musicLP = ctx.createBiquadFilter();
      this.musicLP.type = "lowpass";
      this.musicLP.frequency.value = 18000;
      this.pan = ctx.createStereoPanner ? ctx.createStereoPanner() : (ctx.createGain() as unknown as StereoPannerNode);
      this.musicGain = ctx.createGain();
      this.musicVol = ctx.createGain();
      this.musicVol.gain.value = 0.8;
      this.analyser = ctx.createAnalyser();
      this.analyser.fftSize = 512;
      this.musicLP.connect(this.pan).connect(this.musicGain).connect(this.musicVol).connect(this.analyser).connect(this.master);
      this.el = new Audio();
      this.el.preload = "none";
      this.el.crossOrigin = "anonymous";
      ctx.createMediaElementSource(this.el).connect(this.musicLP);
      this.applyPerspective(true);
    }
    if (this.ctx.state === "suspended") void this.ctx.resume();
  }

  setEnabled(on: boolean) {
    this.enabled = on;
    if (!this.ctx) return;
    const t = this.ctx.currentTime;
    this.master.gain.cancelScheduledValues(t);
    if (on) {
      this.master.gain.setValueAtTime(this.master.gain.value, t);
      this.master.gain.linearRampToValueAtTime(1, t + 0.25);
      void this.startRoom();
    } else {
      this.master.gain.setValueAtTime(0, t); // immediate
    }
  }

  private load(name: SfxName) {
    if (!this.buffers.has(name)) {
      this.buffers.set(
        name,
        fetch(SFX[name])
          .then((r) => r.arrayBuffer())
          .then((b) => this.ctx!.decodeAudioData(b))
          .catch(() => null),
      );
    }
    return this.buffers.get(name)!;
  }

  private async startRoom() {
    if (!this.ctx || this.roomSrc) return;
    const buf = await this.load("room");
    if (!buf || this.roomSrc || !this.ctx) return;
    const src = this.ctx.createBufferSource();
    src.buffer = buf;
    src.loop = true;
    src.connect(this.roomLP);
    src.start();
    this.roomSrc = src;
    this.applyPerspective();
  }

  async sfx(name: SfxName, opts: { gain?: number; rate?: number } = {}) {
    if (!this.ctx || !this.enabled) return;
    const buf = await this.load(name);
    if (!buf || !this.ctx || !this.enabled) return;
    const src = this.ctx.createBufferSource();
    src.buffer = buf;
    src.playbackRate.value = opts.rate ?? 1;
    const g = this.ctx.createGain();
    g.gain.value = opts.gain ?? 1;
    src.connect(g).connect(this.master);
    src.start();
  }

  preload(names: SfxName[]) {
    if (this.ctx) names.forEach((n) => void this.load(n));
  }

  setShot(shot: Shot) {
    this.shot = shot;
    this.applyPerspective();
  }

  private applyPerspective(instant = false) {
    if (!this.ctx) return;
    const p = PERSPECTIVE[this.shot];
    const t = this.ctx.currentTime;
    const tc = instant ? 0.001 : 0.6;
    const duck = this.musicOn ? 0.35 : 1;
    this.roomGain.gain.setTargetAtTime(this.roomSrc ? p.roomGain * duck * 0.5 : 0, t, tc);
    this.roomLP.frequency.setTargetAtTime(p.roomLP, t, tc);
    this.musicLP.frequency.setTargetAtTime(p.musicLP, t, tc);
    this.musicGain.gain.setTargetAtTime(p.musicGain, t, tc);
    if ("pan" in this.pan) this.pan.pan.setTargetAtTime(p.pan, t, tc);
  }

  /** Play a preview; only one at a time. Returns false if playback was blocked. */
  async play(src: string) {
    this.unlock();
    if (!this.el) return false;
    if (!this.el.src.endsWith(src)) {
      this.el.src = src;
      this.el.currentTime = 0;
    }
    try {
      await this.el.play();
      this.musicOn = true;
      this.applyPerspective();
      return true;
    } catch {
      return false;
    }
  }

  pause() {
    this.el?.pause();
    this.musicOn = false;
    this.applyPerspective();
  }

  setVolume(v: number) {
    if (this.musicVol && this.ctx) this.musicVol.gain.setTargetAtTime(v, this.ctx.currentTime, 0.02);
  }

  /** Smoothed 0..1 loudness of the music for the violet light. */
  musicLevel() {
    if (!this.ctx || !this.musicOn || !this.analyser) {
      this.level *= 0.94;
      return this.level;
    }
    this.analyser.getByteTimeDomainData(this.data);
    let sum = 0;
    for (let i = 0; i < this.data.length; i++) {
      const v = (this.data[i] - 128) / 128;
      sum += v * v;
    }
    const rms = Math.min(1, Math.sqrt(sum / this.data.length) * 2.2);
    this.level += (rms - this.level) * (rms > this.level ? 0.25 : 0.06);
    return this.level;
  }
}

export const audio = new Engine();

if (typeof window !== "undefined" && process.env.NODE_ENV !== "production") Object.assign(window, { __audio: audio });
