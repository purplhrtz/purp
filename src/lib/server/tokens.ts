import "server-only";
import crypto from "node:crypto";
import { env } from "./env";

/** Signed, expiring download tokens: base64url(payload).base64url(hmac) */
type Payload = { p: string; s: string; e: number };

const secret = () => {
  if (!env.downloadSecret) throw new Error("DOWNLOAD_SIGNING_SECRET is not set");
  return env.downloadSecret;
};

export function signDownload(productId: string, sessionId: string, ttlSeconds = 60 * 60 * 24) {
  const payload: Payload = { p: productId, s: sessionId, e: Math.floor(Date.now() / 1000) + ttlSeconds };
  const body = Buffer.from(JSON.stringify(payload)).toString("base64url");
  const mac = crypto.createHmac("sha256", secret()).update(body).digest("base64url");
  return `${body}.${mac}`;
}

export function verifyDownload(token: string): Payload | null {
  const [body, mac] = token.split(".");
  if (!body || !mac) return null;
  const expected = crypto.createHmac("sha256", secret()).update(body).digest();
  const given = Buffer.from(mac, "base64url");
  if (given.length !== expected.length || !crypto.timingSafeEqual(given, expected)) return null;
  try {
    const p = JSON.parse(Buffer.from(body, "base64url").toString()) as Payload;
    if (typeof p.e !== "number" || p.e < Date.now() / 1000) return null;
    return p;
  } catch {
    return null;
  }
}
