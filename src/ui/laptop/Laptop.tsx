"use client";
import { useEffect, useRef, useState } from "react";
import { useStore, type Tab } from "@/state/store";
import * as act from "@/state/actions";
import { IconBack } from "../icons";
import { StudioView } from "./StudioView";
import { ListenView } from "./ListenView";
import { ShopView } from "./ShopView";
import { CartView } from "./CartView";

const TABS: { id: Tab; label: string }[] = [
  { id: "studio", label: "Studio" },
  { id: "listen", label: "Listen" },
  { id: "shop", label: "Shop" },
  { id: "cart", label: "Cart" },
];

/** One accessible HTML storefront. Docks onto the laptop's display when it's big enough on screen,
 *  otherwise opens as a close-up panel (desktop) or full-screen (phones). Stays mounted when closed
 *  so scroll position and in-progress state survive trips back into the room. */
export function Laptop({ open, reduced }: { open: boolean; reduced: boolean }) {
  const tab = useStore((s) => s.tab);
  const cart = useStore((s) => s.cart);
  const rect = useStore((s) => s.screenRect);
  const sceneReady = useStore((s) => s.sceneReady);
  const [vw, setVw] = useState({ w: 1280, h: 800 });
  const headRef = useRef<HTMLHeadingElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const on = () => setVw({ w: innerWidth, h: innerHeight });
    on();
    addEventListener("resize", on);
    return () => removeEventListener("resize", on);
  }, []);
  useEffect(() => {
    if (open) window.setTimeout(() => headRef.current?.focus({ preventScroll: true }), reduced ? 0 : 520);
  }, [open, reduced]);
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: 0 });
  }, [tab]);

  const phone = vw.w < 720 || vw.w / vw.h < 0.85;
  const canDock = !phone && sceneReady && rect && rect.w >= 760 && rect.h >= 480;
  const mode = canDock ? "docked" : phone ? "sheet" : "centered";
  const style = canDock && rect ? { left: rect.x, top: rect.y, width: rect.w, height: rect.h } : undefined;

  const onTabKey = (e: React.KeyboardEvent, i: number) => {
    if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
    e.preventDefault();
    const n = (i + (e.key === "ArrowRight" ? 1 : TABS.length - 1)) % TABS.length;
    useStore.getState().setTab(TABS[n].id);
    document.getElementById(`tab-${TABS[n].id}`)?.focus();
  };

  return (
    <section
      className={`panel ${mode}${open ? " open" : ""}`}
      style={style}
      role="dialog"
      aria-modal="false"
      aria-labelledby="laptop-title"
      aria-hidden={!open}
      inert={!open}
    >
      <div className="panel-bar">
        <h2 className="sr-only" id="laptop-title" tabIndex={-1} ref={headRef}>purplhrtz storefront, on the studio laptop</h2>
        <span className="mark" aria-hidden>purplhrtz</span>
        <div className="tabs" role="tablist" aria-label="Storefront sections">
          {TABS.map((t, i) => (
            <button
              key={t.id}
              id={`tab-${t.id}`}
              role="tab"
              className="tab"
              aria-selected={tab === t.id}
              aria-controls="laptop-view"
              tabIndex={tab === t.id ? 0 : -1}
              onKeyDown={(e) => onTabKey(e, i)}
              onClick={() => useStore.getState().setTab(t.id)}
            >
              {t.label}
              {t.id === "cart" && cart.length > 0 && <span className="count" aria-label={`${cart.length} items`}>{cart.length}</span>}
            </button>
          ))}
        </div>
        <button className="btn back" onClick={act.back}><IconBack /> Back to room</button>
      </div>
      <div className="panel-scroll" ref={scrollRef} id="laptop-view" role="tabpanel" aria-labelledby={`tab-${tab}`}>
        {tab === "studio" && <StudioView />}
        {tab === "listen" && <ListenView />}
        {tab === "shop" && <ShopView />}
        {tab === "cart" && <CartView />}
      </div>
    </section>
  );
}
