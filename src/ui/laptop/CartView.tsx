"use client";
import { useEffect, useState } from "react";
import { formatPrice, productById } from "@content/catalog";
import { useStore } from "@/state/store";
import { IconDownload, IconX } from "../icons";

type Verified = { paid: true; items: { id: string; title: string; kind: string; downloadUrl: string }[]; email: string | null; total: number; currency: string };
type Step =
  | { k: "idle" }
  | { k: "busy" }
  | { k: "error"; msg: string }
  | { k: "demo-confirm"; orderId: string; total: number; ids: string[] }
  | { k: "demo-done"; orderId: string; total: number; ids: string[] }
  | { k: "verifying" }
  | { k: "paid"; v: Verified }
  | { k: "pending"; sessionId: string }
  | { k: "cancelled" };

export function CartView() {
  const cart = useStore((s) => s.cart);
  const modes = useStore((s) => s.modes);
  const ret = useStore((s) => s.checkoutReturn);
  const [step, setStep] = useState<Step>({ k: "idle" });
  const items = cart.map((id) => productById(id)).filter(Boolean) as NonNullable<ReturnType<typeof productById>>[];
  const total = items.reduce((s, p) => s + p.priceCents, 0);

  const verify = async (sessionId: string) => {
    setStep({ k: "verifying" });
    try {
      const r = await fetch(`/api/checkout/verify?session_id=${encodeURIComponent(sessionId)}`);
      const j = await r.json();
      if (r.ok && j.paid) {
        useStore.getState().clearCart();
        setStep({ k: "paid", v: j });
      } else if (r.ok) setStep({ k: "pending", sessionId });
      else setStep({ k: "error", msg: j.error || "We couldn't confirm that payment yet." });
    } catch {
      setStep({ k: "error", msg: "We couldn't reach the studio to confirm the payment. Check your connection and try again." });
    }
  };

  useEffect(() => {
    if (!ret) return;
    useStore.getState().set({ checkoutReturn: null });
    if (ret.result === "cancelled") setStep({ k: "cancelled" });
    else if (ret.sessionId) void verify(ret.sessionId);
  }, [ret]);

  const checkout = async () => {
    setStep({ k: "busy" });
    try {
      const r = await fetch("/api/checkout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ items: cart.map((id) => ({ id })) }),
      });
      const j = await r.json();
      if (!r.ok) return setStep({ k: "error", msg: j.error || "Checkout didn't start. Your cart is saved." });
      if (j.mode === "demo") return setStep({ k: "demo-confirm", orderId: j.orderId, total: j.total, ids: j.ids });
      window.location.assign(j.url); // hosted Stripe Checkout
    } catch {
      setStep({ k: "error", msg: "Couldn't reach checkout. Your cart is saved — try again in a moment." });
    }
  };

  if (step.k === "verifying") {
    return <div className="view"><p className="kicker">checkout</p><h3 className="display">confirming…</h3><p className="lede" role="status">Checking the payment with Stripe before unlocking your downloads.</p></div>;
  }
  if (step.k === "paid") {
    return (
      <div className="view">
        <p className="kicker">payment confirmed{modes.stripeTestMode ? " · stripe sandbox" : ""}</p>
        <h3 className="display">thank you</h3>
        <div className="notice ok" role="status">
          <h3>Your downloads are ready.</h3>
          <p>Links are signed for you and expire in 24 hours.{step.v.email ? ` A receipt is on its way to ${step.v.email}.` : ""}</p>
        </div>
        <ul className="cart-list">
          {step.v.items.map((it) => {
            const p = productById(it.id)!;
            return (
              <li className="cart-item" key={it.id}>
                <img src={p.cover.replace(".jpg", "-sm.jpg")} alt="" width={72} height={72} />
                <div><span className="meta">{it.kind}</span><h3>{it.title}</h3></div>
                <a className="btn solid" href={it.downloadUrl} download><IconDownload /> Download</a>
              </li>
            );
          })}
        </ul>
        <button className="btn" onClick={() => useStore.getState().setTab("shop")}>Back to the shop</button>
      </div>
    );
  }
  if (step.k === "pending") {
    return (
      <div className="view">
        <h3 className="display">almost</h3>
        <div className="notice" role="status"><h3>Stripe hasn't marked this as paid yet.</h3><p>Some payment methods take a moment. Nothing unlocks until it's confirmed.</p></div>
        <div className="row"><button className="btn solid" onClick={() => verify(step.sessionId)}>Check again</button><button className="btn" onClick={() => setStep({ k: "idle" })}>Back to cart</button></div>
      </div>
    );
  }
  if (step.k === "demo-confirm" || step.k === "demo-done") {
    const done = step.k === "demo-done";
    return (
      <div className="view">
        <p className="kicker"><span className="badge">demo checkout</span></p>
        <h3 className="display">{done ? "order noted" : "demo checkout"}</h3>
        <div className="notice demo" role="status">
          <h3>{done ? "Demo order complete — nothing was charged." : "This store is in demo mode."}</h3>
          <p>No payment details are collected here. With a Stripe key configured, this button goes to Stripe's hosted checkout instead.</p>
          {done && <p>Demo orders don't unlock downloads. Reference: <code>{step.orderId}</code></p>}
        </div>
        <ul className="cart-list">
          {step.ids.map((id) => {
            const p = productById(id)!;
            return <li className="cart-item" key={id}><img src={p.cover.replace(".jpg", "-sm.jpg")} alt="" width={72} height={72} /><div><span className="meta">{p.kind}</span><h3>{p.title}</h3></div><span className="price">{formatPrice(p.priceCents)}</span></li>;
          })}
        </ul>
        <div className="total"><span>Total</span><strong>{formatPrice(step.total)}</strong></div>
        {done ? (
          <button className="btn solid" onClick={() => { setStep({ k: "idle" }); useStore.getState().setTab("shop"); }}>Back to the shop</button>
        ) : (
          <div className="row">
            <button className="btn solid" onClick={() => { useStore.getState().clearCart(); setStep({ ...step, k: "demo-done" }); }}>Complete demo order</button>
            <button className="btn" onClick={() => setStep({ k: "idle" })}>Back to cart</button>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="view">
      <p className="kicker">
        {modes.checkout === "stripe" ? <span className={`badge${modes.stripeTestMode ? "" : " live"}`}>{modes.stripeTestMode ? "stripe sandbox" : "secure checkout by stripe"}</span> : <span className="badge">demo checkout</span>}
      </p>
      <h3 className="display">your cart</h3>
      {step.k === "cancelled" && (
        <div className="notice" role="status"><h3>Checkout cancelled.</h3><p>Nothing was charged. Your cart is right where you left it.</p></div>
      )}
      {step.k === "error" && (
        <div className="notice error" role="alert"><h3>That didn't go through.</h3><p>{step.msg}</p></div>
      )}
      {items.length === 0 ? (
        <div className="empty">
          <p>Nothing in here yet.</p>
          <button className="btn solid" onClick={() => useStore.getState().setTab("shop")}>Browse the shop</button>
        </div>
      ) : (
        <>
          <ul className="cart-list">
            {items.map((p) => (
              <li className="cart-item" key={p.id}>
                <img src={p.cover.replace(".jpg", "-sm.jpg")} alt="" width={72} height={72} />
                <div><span className="meta">{p.kind}</span><h3>{p.title}</h3><span className="price">{formatPrice(p.priceCents)}</span></div>
                <button className="btn icon-btn" onClick={() => useStore.getState().removeFromCart(p.id)} aria-label={`Remove ${p.title}`}><IconX /></button>
              </li>
            ))}
          </ul>
          <div className="total"><span>Total</span><strong>{formatPrice(total)}</strong></div>
          <div className="row">
            <button className="btn violet" onClick={checkout} disabled={step.k === "busy"}>
              {step.k === "busy" ? "Starting checkout…" : modes.checkout === "stripe" ? "Check out with Stripe" : "Check out (demo)"}
            </button>
            <button className="btn" onClick={() => useStore.getState().setTab("shop")}>Keep browsing</button>
          </div>
          <p className="meta" style={{ marginTop: 14 }}>Digital downloads · one license each · prices in USD</p>
        </>
      )}
    </div>
  );
}
