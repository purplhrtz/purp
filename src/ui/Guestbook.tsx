"use client";
import { useEffect, useRef, useState } from "react";
import { useStore } from "@/state/store";
import * as act from "@/state/actions";
import { IconBack } from "./icons";

type Note = { id: string; display_name: string | null; body: string; created_at: string; local?: boolean };
const LOCAL = "purplhrtz-notes-local";
const DRAFT = "purplhrtz-note-draft";
const MAX = 280;

const readLocal = (): Note[] => {
  try {
    return JSON.parse(localStorage.getItem(LOCAL) || "[]");
  } catch {
    return [];
  }
};
const tilt = (id: string) => ((id.charCodeAt(0) + id.charCodeAt(id.length - 1)) % 7) - 3;
const when = (iso: string) => new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric" });

export function Guestbook({ open }: { open: boolean }) {
  const serverMode = useStore((s) => s.modes.notes);
  const [mode, setMode] = useState<"shared" | "demo">(serverMode);
  const [shared, setShared] = useState<Note[]>([]);
  const [local, setLocal] = useState<Note[]>([]);
  const [name, setName] = useState("");
  const [body, setBody] = useState("");
  const [status, setStatus] = useState<{ kind: "ok" | "error" | "busy" | ""; msg: string; offerLocal?: boolean }>({ kind: "", msg: "" });
  const [loadErr, setLoadErr] = useState("");
  const headRef = useRef<HTMLHeadingElement>(null);
  const hp = useRef<HTMLInputElement>(null);

  useEffect(() => setMode(serverMode), [serverMode]);
  useEffect(() => {
    setLocal(readLocal());
    try {
      const d = JSON.parse(localStorage.getItem(DRAFT) || "{}");
      if (d.body) setBody(d.body);
      if (d.name) setName(d.name);
    } catch {}
  }, []);
  useEffect(() => {
    try {
      localStorage.setItem(DRAFT, JSON.stringify({ name, body }));
    } catch {}
  }, [name, body]);
  useEffect(() => {
    if (!open) return;
    window.setTimeout(() => headRef.current?.focus({ preventScroll: true }), 500);
    if (serverMode !== "shared") return;
    fetch("/api/notes", { cache: "no-store" })
      .then(async (r) => {
        const j = await r.json();
        if (j.mode) setMode(j.mode);
        setShared(j.notes || []);
        setLoadErr(r.ok ? "" : j.error || "The shared board is out of reach.");
      })
      .catch(() => setLoadErr("The shared board is out of reach right now."));
  }, [open, serverMode]);

  const saveLocal = () => {
    const n: Note = { id: `local-${Date.now()}`, display_name: name.trim() || null, body: body.trim().slice(0, MAX), created_at: new Date().toISOString(), local: true };
    const next = [n, ...readLocal()].slice(0, 40);
    try {
      localStorage.setItem(LOCAL, JSON.stringify(next));
    } catch {}
    setLocal(next);
    setBody("");
    setStatus({ kind: "ok", msg: "Pinned — on this device only." });
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const text = body.trim();
    if (!text) return setStatus({ kind: "error", msg: "Write something first." });
    if (text.length > MAX) return setStatus({ kind: "error", msg: `Keep it under ${MAX} characters.` });
    if (mode === "demo") return saveLocal();
    setStatus({ kind: "busy", msg: "Pinning…" });
    try {
      const r = await fetch("/api/notes", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: name.trim(), body: text, website: hp.current?.value || "" }),
      });
      const j = await r.json().catch(() => ({}));
      if (r.ok && j.note) {
        setShared((s) => [j.note, ...s]);
        setBody("");
        setStatus({ kind: "ok", msg: "Pinned to the board. Thanks for stopping by." });
      } else {
        // keep the draft; offer a device-only pin when the shared board isn't available
        setStatus({ kind: "error", msg: j.error || "Couldn't pin that. Your draft is saved.", offerLocal: r.status === 503 });
      }
    } catch {
      setStatus({ kind: "error", msg: "No connection. Your draft is saved — try again.", offerLocal: true });
    }
  };

  const all = [...local, ...shared];
  const left = MAX - body.length;

  return (
    <section className={`panel sheet cork${open ? " open" : ""}`} role="dialog" aria-modal="false" aria-labelledby="cork-title" aria-hidden={!open} inert={!open}>
      <div className="panel-bar">
        <h2 className="panel-title" id="cork-title" tabIndex={-1} ref={headRef}>the corkboard</h2>
        <button className="btn back" onClick={act.back}><IconBack /> Back to room</button>
      </div>
      <div className="panel-scroll">
        <div className="board">
          <form className="note-form" onSubmit={submit} noValidate>
            <span className="pin" aria-hidden />
            <h2>leave a note</h2>
            <p>{mode === "shared" ? "Pinned for everyone who comes down the stairs." : "Demo mode: notes stay on this device only."}</p>
            <label htmlFor="note-name">Name (optional)</label>
            <input id="note-name" value={name} maxLength={32} autoComplete="nickname" onChange={(e) => setName(e.target.value)} />
            <label htmlFor="note-body">Message</label>
            <textarea id="note-body" value={body} maxLength={MAX + 20} required aria-describedby="note-count note-status" onChange={(e) => setBody(e.target.value)} />
            <div className="hp" aria-hidden><label>Website<input ref={hp} tabIndex={-1} autoComplete="off" name="website" /></label></div>
            <div className="row">
              <button className="btn solid" type="submit" disabled={status.kind === "busy"}>{status.kind === "busy" ? "Pinning…" : "Pin it"}</button>
              <span className="counter" id="note-count" aria-live="polite">{left < 40 ? `${left} left` : `${body.length}/${MAX}`}</span>
            </div>
            <p className={`status ${status.kind}`} id="note-status" role={status.kind === "error" ? "alert" : "status"}>{status.msg}</p>
            {status.offerLocal && body.trim() && (
              <button type="button" className="btn" onClick={saveLocal} style={{ borderColor: "#231a28", color: "#231a28" }}>Keep it on this device instead</button>
            )}
          </form>
          <div>
            <p className="wall-label">{mode === "shared" ? "notes from visitors" : "notes on this device (demo)"}{loadErr ? ` — ${loadErr}` : ""}</p>
            <ul className="notes-wall">
              <li className="note flyer" style={{ transform: "rotate(2deg)" }} aria-hidden><img src="/media/textures/flyer_a.jpg" alt="" width={600} height={840} /></li>
              {all.map((n, i) => (
                <li key={n.id} className={`note${n.local ? " local" : ""}`} style={{ transform: `rotate(${tilt(n.id)}deg)` }}>
                  <span className="pin" aria-hidden />
                  <p>{n.body}</p>
                  <footer>
                    <span>— {n.display_name || "anonymous"}</span>
                    <span>{n.local ? "this device only" : when(n.created_at)}</span>
                  </footer>
                </li>
              )).flatMap((el, i) => (i === 2 ? [el, <li key="flyer-c" className="note flyer" style={{ transform: "rotate(-3deg)" }} aria-hidden><img src="/media/textures/flyer_c.jpg" alt="" width={600} height={840} /></li>] : [el]))}
              {all.length === 0 && (
                <li className="note" style={{ transform: "rotate(-1.5deg)" }}>
                  <span className="pin" aria-hidden />
                  <p>Nothing pinned yet. Be the first — say hi to Barry.</p>
                  <footer><span>— the studio</span><span /></footer>
                </li>
              )}
              <li className="note flyer" style={{ transform: "rotate(-1deg)" }} aria-hidden><img src="/media/textures/flyer_b.jpg" alt="" width={600} height={840} /></li>
            </ul>
          </div>
        </div>
      </div>
    </section>
  );
}
