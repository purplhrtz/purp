import { NextResponse } from "next/server";
import { productById } from "@content/catalog";
import { env, modes } from "@/lib/server/env";
import { stripe } from "@/lib/server/stripe";
import { allow, clientIp } from "@/lib/server/ratelimit";

export const runtime = "nodejs";

function origin(req: Request) {
  if (env.siteUrl) return env.siteUrl.replace(/\/$/, "");
  const h = req.headers;
  const host = h.get("x-forwarded-host") || h.get("host");
  const proto = h.get("x-forwarded-proto") || "http";
  return host ? `${proto}://${host}` : new URL(req.url).origin;
}

export async function POST(req: Request) {
  if (!allow(`checkout:${clientIp(req)}`, 10, 60_000)) {
    return NextResponse.json({ error: "Too many checkout attempts. Try again in a minute." }, { status: 429 });
  }
  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "Invalid request." }, { status: 400 });
  }
  const items = (body as { items?: unknown })?.items;
  if (!Array.isArray(items) || items.length < 1 || items.length > 10) {
    return NextResponse.json({ error: "Your cart is empty." }, { status: 400 });
  }
  // Digital goods: one of each. Prices come only from the server-side catalog.
  const ids = [...new Set(items.map((i) => String((i as { id?: unknown })?.id ?? "")))];
  const products = ids.map((id) => productById(id));
  if (products.some((p) => !p)) {
    return NextResponse.json({ error: "Something in your cart is no longer for sale." }, { status: 400 });
  }
  const list = products as NonNullable<(typeof products)[number]>[];
  const total = list.reduce((s, p) => s + p.priceCents, 0);

  if (modes().checkout === "demo") {
    return NextResponse.json({ mode: "demo", orderId: `demo_${Date.now().toString(36)}`, total, ids });
  }

  try {
    const base = origin(req);
    const session = await stripe().checkout.sessions.create({
      mode: "payment",
      line_items: list.map((p) =>
        p.stripePriceId
          ? { price: p.stripePriceId, quantity: 1 }
          : {
              quantity: 1,
              price_data: {
                currency: p.currency,
                unit_amount: p.priceCents,
                product_data: { name: `purplhrtz — ${p.title}`, description: p.tagline, metadata: { product_id: p.id } },
              },
            },
      ),
      metadata: { product_ids: list.map((p) => p.id).join(",") },
      payment_intent_data: { metadata: { product_ids: list.map((p) => p.id).join(",") } },
      success_url: `${base}/?checkout=success&session_id={CHECKOUT_SESSION_ID}`,
      cancel_url: `${base}/?checkout=cancelled`,
    });
    return NextResponse.json({ mode: "stripe", url: session.url });
  } catch (err) {
    console.error("[checkout] stripe session failed", err);
    return NextResponse.json({ error: "Checkout is unavailable right now. Your cart is saved." }, { status: 502 });
  }
}
