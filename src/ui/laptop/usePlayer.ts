"use client";
import { useEffect, useState } from "react";
import { audio } from "@/audio/engine";
import { useStore } from "@/state/store";

/** Progress for the single shared preview player. */
export function usePlayer() {
  const playing = useStore((s) => s.playing);
  const [t, setT] = useState({ cur: 0, dur: 0 });
  useEffect(() => {
    let raf = 0;
    const tick = () => {
      const el = audio.el;
      if (el) setT({ cur: el.currentTime || 0, dur: Number.isFinite(el.duration) ? el.duration : 0 });
      raf = requestAnimationFrame(tick);
    };
    const el = audio.el;
    const onEnd = () => useStore.getState().setPlaying(false);
    el?.addEventListener("ended", onEnd);
    if (playing) raf = requestAnimationFrame(tick);
    else tick(), cancelAnimationFrame(raf);
    return () => {
      cancelAnimationFrame(raf);
      el?.removeEventListener("ended", onEnd);
    };
  }, [playing]);
  return t;
}

export const fmt = (s: number) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;
