import "server-only";
import crypto from "node:crypto";
import { env } from "./env";

/** Best-effort in-memory limiter (per server instance). The database enforces the real limit. */
const hits = new Map<string, number[]>();

export function allow(key: string, limit: number, windowMs: number) {
  const now = Date.now();
  const list = (hits.get(key) || []).filter((t) => now - t < windowMs);
  if (list.length >= limit) {
    hits.set(key, list);
    return false;
  }
  list.push(now);
  hits.set(key, list);
  if (hits.size > 5000) for (const [k, v] of hits) if (!v.some((t) => now - t < windowMs)) hits.delete(k);
  return true;
}

export function clientIp(req: Request) {
  const fwd = req.headers.get("x-forwarded-for");
  return (fwd ? fwd.split(",")[0] : req.headers.get("x-real-ip")) || "0.0.0.0";
}

export function hashIp(ip: string) {
  return crypto.createHash("sha256").update(`${env.ipSalt}:${ip}`).digest("hex");
}
