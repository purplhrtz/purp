import { NextResponse } from "next/server";
import type Stripe from "stripe";
import { env } from "@/lib/server/env";
import { stripe } from "@/lib/server/stripe";
import { recordPaidOrder } from "@/lib/server/orders";

export const runtime = "nodejs";

export async function POST(req: Request) {
  if (!env.stripeKey || !env.stripeWebhookSecret) {
    return NextResponse.json({ error: "webhooks not configured" }, { status: 503 });
  }
  const sig = req.headers.get("stripe-signature") || "";
  const raw = await req.text();
  let event: Stripe.Event;
  try {
    event = stripe().webhooks.constructEvent(raw, sig, env.stripeWebhookSecret);
  } catch {
    return NextResponse.json({ error: "bad signature" }, { status: 400 });
  }
  if (event.type === "checkout.session.completed" || event.type === "checkout.session.async_payment_succeeded") {
    const session = event.data.object as Stripe.Checkout.Session;
    if (session.payment_status !== "paid") {
      return NextResponse.json({ received: true, fulfilled: false, reason: "not paid yet" });
    }
    try {
      const first = await recordPaidOrder(event.id, event.type, session);
      // Repeat deliveries of the same event are acknowledged without doing anything twice.
      return NextResponse.json({ received: true, fulfilled: first, duplicate: !first });
    } catch (err) {
      console.error("[webhook] could not record order", err);
      return NextResponse.json({ error: "temporary failure" }, { status: 500 }); // Stripe will retry
    }
  }
  return NextResponse.json({ received: true });
}
