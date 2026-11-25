import "server-only";
import { env } from "./env";

export class RpcError extends Error {
  constructor(public code: string, public status: number, message: string) {
    super(message);
  }
}

/** Call a Postgres function through PostgREST with the publishable key.
 *  Tables are locked by RLS; only these SECURITY DEFINER functions are reachable. */
export async function rpc<T>(fn: string, args: Record<string, unknown>): Promise<T> {
  const res = await fetch(`${env.supabaseUrl}/rest/v1/rpc/${fn}`, {
    method: "POST",
    headers: {
      apikey: env.supabaseAnonKey,
      Authorization: `Bearer ${env.supabaseAnonKey}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(args),
    cache: "no-store",
    signal: AbortSignal.timeout(8000),
  });
  if (!res.ok) {
    let body: { message?: string; code?: string } = {};
    try {
      body = await res.json();
    } catch {}
    throw new RpcError(body.code || String(res.status), res.status, body.message || res.statusText);
  }
  return (await res.json()) as T;
}
