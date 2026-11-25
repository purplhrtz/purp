import "server-only";

/** Which integrations are live. Everything degrades to a labelled demo mode when unset. */
export const env = {
  stripeKey: process.env.STRIPE_SECRET_KEY || "",
  stripeWebhookSecret: process.env.STRIPE_WEBHOOK_SECRET || "",
  supabaseUrl: (process.env.SUPABASE_URL || "").replace(/\/$/, ""),
  supabaseAnonKey: process.env.SUPABASE_ANON_KEY || "",
  supabaseServerToken: process.env.SUPABASE_SERVER_RPC_TOKEN || "",
  ipSalt: process.env.NOTES_IP_SALT || "",
  downloadSecret: process.env.DOWNLOAD_SIGNING_SECRET || "",
  siteUrl: process.env.NEXT_PUBLIC_SITE_URL || "",
};

export const modes = () => ({
  checkout: env.stripeKey ? ("stripe" as const) : ("demo" as const),
  notes: env.supabaseUrl && env.supabaseAnonKey && env.supabaseServerToken && env.ipSalt ? ("shared" as const) : ("demo" as const),
  stripeTestMode: env.stripeKey.startsWith("sk_test_") || env.stripeKey.startsWith("rk_test_"),
});
