import { NextResponse } from "next/server";
import { productById } from "@content/catalog";
import { modes } from "@/lib/server/env";
import { stripe } from "@/lib/server/stripe";
import { productIdsFromSession, recordPaidOrder } from "@/lib/server/orders";
import { signDownload } from "@/lib/server/tokens";

export const runtime = "nodejs";

/** Confirms a Checkout Session with Stripe (never trusts the redirect alone) and returns signed links. */
export async function GET(req: Request) {
  const id = new URL(req.url).searchParams.get("session_id") || "";
  if (!/^cs_(test|live)_[A-Za-z0-9]{10,200}$/.test(id)) {
    return NextResponse.json({ error: "Unknown checkout session." }, { status: 400 });
  }
  if (modes().checkout !== "stripe") {
    return NextResponse.json({ error: "Checkout isn't configured." }, { status: 503 });
  }
  try {
    const session = await stripe().checkout.sessions.retrieve(id);
    if (session.payment_status !== "paid") {
      return NextResponse.json({ paid: false, status: session.status, payment_status: session.payment_status });
    }
    // Record here too, so downloads work even if the webhook is delayed. Idempotent by session.
    await recordPaidOrder(`verify:${session.id}`, "checkout.session.verified", session);
    const items = productIdsFromSession(session).map((pid) => {
      const p = productById(pid)!;
      return { id: p.id, title: p.title, kind: p.kind, downloadUrl: `/api/download/${signDownload(p.id, session.id)}` };
    });
    return NextResponse.json({ paid: true, items, email: session.customer_details?.email ?? null, total: session.amount_total, currency: session.currency });
  } catch (err) {
    console.error("[verify] failed", err);
    return NextResponse.json({ error: "Couldn't confirm the payment yet." }, { status: 502 });
  }
}
