import "server-only";
import Stripe from "stripe";
import { env } from "./env";

let client: Stripe | null = null;
export function stripe() {
  if (!env.stripeKey) throw new Error("STRIPE_SECRET_KEY is not set");
  // fetch-based client: works on Node, edge-friendly runtimes, and behind HTTPS proxies
  client ??= new Stripe(env.stripeKey, { appInfo: { name: "purplhrtz" }, httpClient: Stripe.createFetchHttpClient() });
  return client;
}
