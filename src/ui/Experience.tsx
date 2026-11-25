"use client";
import dynamic from "next/dynamic";
import { useCallback, useEffect, useRef, useState } from "react";
import { useStore, type Modes } from "@/state/store";
import * as act from "@/state/actions";
import { audio } from "@/audio/engine";
import { Laptop } from "./laptop/Laptop";
import { Guestbook } from "./Guestbook";
import { FallbackHotspots } from "./FallbackHotspots";
import { SceneBoundary } from "./SceneBoundary";
import { IconBack, IconCat, IconCouch, IconLamp, IconLaptop, IconPause, IconPin, IconSoundOff, IconSoundOn, IconSpeaker } from "./icons";

const Studio = dynamic(() => import("@/scene/Studio"), { ssr: false });

function hasWebGL() {
  try {
    const c = document.createElement("canvas");
    return !!(c.getContext("webgl2") || c.getContext("webgl"));
  } catch {
    return false;
  }
}

export default function Experience({ modes }: { modes: Modes }) {
  const shot = useStore((s) => s.shot);
  const panel = useStore((s) => s.panel);
  const soundOn = useStore((s) => s.soundOn);
  const lampOn = useStore((s) => s.lampOn);
  const playing = useStore((s) => s.playing);
  const introDone = useStore((s) => s.introDone);
  const sceneReady = useStore((s) => s.sceneReady);
  const webgl = useStore((s) => s.webgl);
  const announce = useStore((s) => s.announce);
  const [reduced, setReduced] = useState(false);
  const [load3d, setLoad3d] = useState(false);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    useStore.getState().setModes(modes);
    setHydrated(true);
    const mq = matchMedia("(prefers-reduced-motion: reduce)");
    setReduced(mq.matches);
    const onChange = () => setReduced(mq.matches);
    mq.addEventListener("change", onChange);
    const ok = hasWebGL() && !new URLSearchParams(location.search).has("nowebgl");
    useStore.getState().set({ webgl: ok ? "yes" : "no" });
    // bring the 3D room in after the still and the controls are up
    let id = 0;
    if (ok) {
      const ric = (window as unknown as { requestIdleCallback?: (cb: () => void, o?: { timeout: number }) => number }).requestIdleCallback;
      id = ric ? ric(() => setLoad3d(true), { timeout: 1200 }) : window.setTimeout(() => setLoad3d(true), 300);
    }
    return () => mq.removeEventListener("change", onChange);
  }, [modes]);

  // return from Stripe Checkout
  useEffect(() => {
    const q = new URLSearchParams(location.search);
    const result = q.get("checkout");
    if (!result) return;
    const sid = q.get("session_id");
    useStore.getState().set({ checkoutReturn: { result: result === "success" ? "success" : "cancelled", sessionId: sid } });
    useStore.getState().openLaptop(null, "cart");
    history.replaceState(null, "", location.pathname);
  }, []);

  // Escape returns to the room; focus goes back to whatever opened the view
  const lastShot = useRef(shot);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && useStore.getState().shot !== "overview") {
        e.preventDefault();
        act.back();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
  useEffect(() => {
    if (lastShot.current !== "overview" && shot === "overview") {
      const id = useStore.getState().returnFocus;
      window.setTimeout(() => (id ? document.getElementById(id) : null)?.focus(), 30);
    }
    if (shot !== "overview" && !panel) {
      window.setTimeout(() => document.getElementById("ctl-back")?.focus(), 30);
    }
    lastShot.current = shot;
  }, [shot, panel]);

  const skip = useCallback(() => {
    act.go("overview");
  }, []);

  const focused = shot !== "overview";
  const showDock = !panel;
  const cls = `stage${reduced ? " reduced" : ""}`;

  return (
    <main className={cls} aria-label="purplhrtz — a basement recording studio after midnight">
      <h1 className="sr-only">purplhrtz — independent music studio</h1>
      <p className="sr-only">
        You are at the bottom of the basement stairs. A warm desk lamp lights a laptop, the edge of the desk and a MIDI
        controller. Violet light grazes the acoustic panels behind the studio monitors. Barry, an orange tabby, is half
        asleep on a blanket on the road case. Use the controls to open the laptop storefront, visit Barry, read the
        corkboard, sit on the couch, switch the lamp or play the monitors.
      </p>
      <div className="stage-still" aria-hidden>
        <picture>
          <source media="(max-aspect-ratio: 17/20)" srcSet="/stills/overview_portrait.webp" type="image/webp" />
          <source media="(max-aspect-ratio: 17/20)" srcSet="/stills/overview_portrait.jpg" />
          <source srcSet="/stills/overview.webp" type="image/webp" />
          <img src="/stills/overview.jpg" alt="" fetchPriority="high" decoding="async" />
        </picture>
      </div>
      {load3d && webgl === "yes" && (
        <div className={`stage-canvas${sceneReady ? " ready" : ""}`} tabIndex={0} aria-label="The studio. Drag or use the arrow keys to look around.">
          <SceneBoundary><Studio reducedMotion={reduced} /></SceneBoundary>
        </div>
      )}
      <div className="vignette" aria-hidden />
      <div className="grain" aria-hidden />

      <div className="chrome">
        <div className="wordmark" aria-hidden>purplhrtz<small>est. basement</small></div>
        <div className="top-right">
          <button className="chip" id="ctl-sound" aria-pressed={soundOn} onClick={() => act.setSound(!soundOn)}>
            {soundOn ? <IconSoundOn /> : <IconSoundOff />}
            <span>{soundOn ? "Sound on" : "Sound off"}</span>
          </button>
        </div>
        {webgl === "yes" && load3d && !sceneReady && <p className="loading-note" aria-hidden>lighting the room…</p>}
        {webgl === "no" && !focused && <FallbackHotspots />}
        {!introDone && sceneReady && !reduced && (
          <button className="chip skip" onClick={skip}>Skip intro</button>
        )}

        {showDock && (
          <nav className="dock" aria-label="Studio controls">
            {focused ? (
              <button className="btn-primary" id="ctl-back" onClick={act.back}><IconBack /> Back to room</button>
            ) : (
              <button className="btn-primary" id="ctl-laptop" onClick={() => act.openLaptop("ctl-laptop")}>
                <IconLaptop /> Open laptop
              </button>
            )}
            <div className="dock-actions">
              {shot !== "barry" && <button className="chip" id="ctl-barry" onClick={() => act.pokeBarry("ctl-barry")}><IconCat /> Barry</button>}
              {shot === "barry" && <button className="chip" id="ctl-pet" onClick={() => act.pokeBarry()}><IconCat /> Say hi again</button>}
              <button className="chip" id="ctl-cork" onClick={() => act.go("cork", "ctl-cork")}><IconPin /> Corkboard</button>
              {shot !== "couch" && <button className="chip" id="ctl-couch" onClick={() => act.go("couch", "ctl-couch")}><IconCouch /> Couch</button>}
              <button className="chip" id="ctl-lamp" aria-pressed={lampOn} onClick={act.toggleLamp}><IconLamp /> Lamp {lampOn ? "on" : "off"}</button>
              <button className="chip" id="ctl-monitors" aria-pressed={playing} onClick={act.toggleMonitors}>
                {playing ? <IconPause /> : <IconSpeaker />} Monitors{playing ? " — pause" : ""}
              </button>
            </div>
            {!focused && webgl === "yes" && <span className="dock-hint" aria-hidden>drag to look around · tap things</span>}
          </nav>
        )}
      </div>

      <div className="panel-layer">
        <Laptop open={panel === "laptop"} reduced={reduced} />
        <Guestbook open={panel === "cork"} />
      </div>
      <div className="sr-only" role="status" aria-live="polite">{announce}</div>
      <AudioSync />
    </main>
  );
}

/** Keeps the engine in sync with the persisted sound preference after the first gesture. */
function AudioSync() {
  const soundOn = useStore((s) => s.soundOn);
  useEffect(() => {
    audio.setEnabled(soundOn);
  }, [soundOn]);
  useEffect(() => {
    const first = () => {
      audio.unlock();
      audio.setEnabled(useStore.getState().soundOn);
      audio.preload(["click", "startup", "tick"]);
    };
    window.addEventListener("pointerdown", first, { once: true });
    window.addEventListener("keydown", first, { once: true });
    return () => {
      window.removeEventListener("pointerdown", first);
      window.removeEventListener("keydown", first);
    };
  }, []);
  return null;
}
