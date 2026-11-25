"use client";
import { tracks } from "@content/catalog";
import { audio } from "@/audio/engine";
import { useStore, type Shot } from "./store";

const s = () => useStore.getState();

/** Call at the top of every user-initiated action: unlocks audio inside the gesture. */
function gesture() {
  audio.unlock();
  audio.setEnabled(s().soundOn);
}

export function openLaptop(from?: string | null) {
  gesture();
  const wasAwake = s().laptopAwake;
  s().openLaptop(from ?? null);
  audio.setShot("desk");
  if (!wasAwake) void audio.sfx("startup", { gain: 0.7 });
}

export function go(shot: Shot, from?: string | null) {
  gesture();
  s().go(shot, shot === "cork" ? "cork" : null, from ?? null);
  audio.setShot(shot);
}

export function back() {
  gesture();
  s().back();
  audio.setShot("overview");
}

export function toggleLamp() {
  gesture();
  s().toggleLamp();
  void audio.sfx("click", { gain: 0.8, rate: s().lampOn ? 1 : 0.92 });
}

export function setSound(on: boolean) {
  audio.unlock();
  s().setSound(on);
  audio.setEnabled(on);
}

export async function playTrack(t: { id: string; title: string; src: string; cover: string }) {
  gesture();
  // Pressing play is an explicit request for sound.
  if (!s().soundOn) setSound(true);
  const cur = s().nowPlaying;
  if (cur?.id === t.id && s().playing) {
    audio.pause();
    s().setPlaying(false);
    return;
  }
  s().setNowPlaying(t, true);
  const ok = await audio.play(t.src);
  if (!ok) s().setPlaying(false);
}

export function pauseMusic() {
  audio.pause();
  s().setPlaying(false);
}

/** Tap the studio monitors: start or pause the preview. */
export function toggleMonitors() {
  gesture();
  if (s().playing) return pauseMusic();
  const t = s().nowPlaying ?? tracks[0];
  void playTrack(t);
}

export function pokeBarry(from?: string | null) {
  if (s().shot !== "barry") go("barry", from);
  else s().set({ barryPoke: s().barryPoke + 1 });
}
