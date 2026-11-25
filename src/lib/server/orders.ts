import "server-only";
import type Stripe from "stripe";
import { productById } from "@content/catalog";
import { env, modes } from "./env";
import { rpc } from "./supabase";

/** Dev fallback when Supabase isn't configured: per-instance memory (not durable). */
const memEvents = new Set<string>();
const memOrders = new Map<string, string[]>();

export function productIdsFromSession(session: Stripe.Checkout.Session): string[] {
  const raw = session.metadata?.product_ids || "";
  return raw.split(",").filter((id) => !!productById(id));
}

/** Idempotently record a paid order. Returns true only the first time this event is seen. */
export async function recordPaidOrder(eventId: string, eventType: string, session: Stripe.Checkout.Session) {
  const ids = productIdsFromSession(session);
  if (modes().notes === "shared") {
    return rpc<boolean>("record_paid_order", {
      p_token: env.supabaseServerToken,
      p_event_id: eventId,
      p_event_type: eventType,
      p_session_id: session.id,
      p_product_ids: ids,
      p_amount_total: session.amount_total ?? null,
      p_currency: session.currency ?? null,
      p_email: session.customer_details?.email ?? null,
    });
  }
  if (memEvents.has(eventId)) return false;
  memEvents.add(eventId);
  if (!memOrders.has(session.id)) memOrders.set(session.id, ids);
  return true;
}

export async function findOrder(sessionId: string): Promise<string[] | null> {
  if (modes().notes === "shared") {
    const rows = await rpc<{ product_ids: string[] }[]>("get_order", { p_token: env.supabaseServerToken, p_session_id: sessionId });
    return rows[0]?.product_ids ?? null;
  }
  return memOrders.get(sessionId) ?? null;
}
