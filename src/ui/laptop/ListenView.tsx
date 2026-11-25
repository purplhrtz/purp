"use client";
import { useState } from "react";
import { tracks } from "@content/catalog";
import { useStore } from "@/state/store";
import * as act from "@/state/actions";
import { audio } from "@/audio/engine";
import { IconPause, IconPlay } from "../icons";
import { fmt, usePlayer } from "./usePlayer";

export function Player() {
  const now = useStore((s) => s.nowPlaying);
  const playing = useStore((s) => s.playing);
  const { cur, dur } = usePlayer();
  const [vol, setVol] = useState(0.8);
  if (!now) return null;
  const pct = dur ? (cur / dur) * 100 : 0;
  return (
    <div className="player" aria-label="Preview player">
      <div className="player-row">
        <button className="btn solid icon-btn" onClick={() => act.playTrack(now)} aria-label={playing ? `Pause ${now.title}` : `Play ${now.title}`}>
          {playing ? <IconPause /> : <IconPlay />}
        </button>
        <div style={{ minWidth: 0 }}>
          <div className="meta">now playing</div>
          <strong>{now.title}</strong>
        </div>
      </div>
      <div className="player-row">
        <label className="sr-only" htmlFor="seek">Position</label>
        <input id="seek" className="range" type="range" min={0} max={dur || 1} step={0.1} value={cur}
          style={{ ["--pct" as string]: `${pct}%` }}
          aria-valuetext={`${fmt(cur)} of ${fmt(dur)}`}
          onChange={(e) => { if (audio.el) audio.el.currentTime = Number(e.target.value); }} />
        <span className="time">{fmt(cur)} / {fmt(dur)}</span>
      </div>
      <div className="player-row">
        <label className="meta" htmlFor="vol">volume</label>
        <input id="vol" className="range vol" type="range" min={0} max={1} step={0.01} value={vol}
          style={{ ["--pct" as string]: `${vol * 100}%` }}
          onChange={(e) => { const v = Number(e.target.value); setVol(v); audio.setVolume(v); }} />
      </div>
    </div>
  );
}

export function ListenView() {
  const now = useStore((s) => s.nowPlaying);
  const playing = useStore((s) => s.playing);
  return (
    <div className="view">
      <p className="kicker">previews · one at a time</p>
      <h3 className="display">listen</h3>
      <p className="lede">Rough bounces straight off the desk. Press play — the monitors in the room will pick it up.</p>
      <ul className="tracks">
        {tracks.map((t) => {
          const active = now?.id === t.id;
          return (
            <li key={t.id} className="track" data-active={active}>
              <img src={t.cover.replace(".jpg", "-sm.jpg")} alt="" width={64} height={64} loading="lazy" />
              <div>
                <h3>{t.title}</h3>
                <p>{t.note} · {t.duration}</p>
              </div>
              <button className={`btn ${active && playing ? "solid" : ""} icon-btn`} onClick={() => act.playTrack(t)}
                aria-label={active && playing ? `Pause ${t.title}` : `Play ${t.title}`} aria-pressed={active && playing}>
                {active && playing ? <IconPause /> : <IconPlay />}
              </button>
            </li>
          );
        })}
      </ul>
      <Player />
    </div>
  );
}
