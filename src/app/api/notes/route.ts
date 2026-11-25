import { NextResponse } from "next/server";
import { env, modes } from "@/lib/server/env";
import { allow, clientIp, hashIp } from "@/lib/server/ratelimit";
import { RpcError, rpc } from "@/lib/server/supabase";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

type Note = { id: string; display_name: string | null; body: string; created_at: string };

const clean = (s: string, max: number) =>
  s
    .normalize("NFC")
    .replace(/[\u0000-\u0009\u000B-\u001F\u007F​-‏‪-‮⁦-⁩]/g, "")
    .replace(/\n{3,}/g, "\n\n")
    .trim()
    .slice(0, max + 1);

export async function GET() {
  if (modes().notes !== "shared") return NextResponse.json({ mode: "demo", notes: [] });
  try {
    const notes = await rpc<Note[]>("list_guestbook_notes", { p_limit: 60 });
    return NextResponse.json({ mode: "shared", notes }, { headers: { "Cache-Control": "no-store" } });
  } catch (err) {
    console.error("[notes] list failed", err);
    return NextResponse.json({ mode: "shared", notes: [], error: "The corkboard is out of reach right now." }, { status: 503 });
  }
}

export async function POST(req: Request) {
  if (modes().notes !== "shared") {
    return NextResponse.json({ error: "Shared notes aren't switched on — your note stays on this device.", mode: "demo" }, { status: 503 });
  }
  if (Number(req.headers.get("content-length") || 0) > 4096) {
    return NextResponse.json({ error: "That note is too long." }, { status: 413 });
  }
  let input: { name?: unknown; body?: unknown; website?: unknown };
  try {
    input = await req.json();
  } catch {
    return NextResponse.json({ error: "Invalid request." }, { status: 400 });
  }
  if (typeof input.website === "string" && input.website.length > 0) {
    return NextResponse.json({ ok: true }); // honeypot: pretend success
  }
  const body = clean(typeof input.body === "string" ? input.body : "", 280);
  const name = clean(typeof input.name === "string" ? input.name : "", 32);
  if (body.length < 1) return NextResponse.json({ error: "Write something first." }, { status: 400 });
  if (body.length > 280) return NextResponse.json({ error: "Keep it under 280 characters." }, { status: 400 });
  if (name.length > 32) return NextResponse.json({ error: "Names top out at 32 characters." }, { status: 400 });

  const ipHash = hashIp(clientIp(req));
  if (!allow(`note:${ipHash}`, 3, 10 * 60_000) || !allow("note:global", 30, 60_000)) {
    return NextResponse.json({ error: "Easy — the board needs a minute. Try again shortly." }, { status: 429 });
  }
  try {
    const rows = await rpc<Note[]>("post_guestbook_note", {
      p_token: env.supabaseServerToken,
      p_ip_hash: ipHash,
      p_display_name: name || null,
      p_body: body,
    });
    return NextResponse.json({ note: rows[0] }, { status: 201 });
  } catch (err) {
    if (err instanceof RpcError) {
      if (/rate_limited/.test(err.message)) return NextResponse.json({ error: "Easy — the board needs a minute. Try again shortly." }, { status: 429 });
      if (/invalid_/.test(err.message)) return NextResponse.json({ error: "That note couldn't be pinned. Check the length." }, { status: 400 });
      if (/unauthorized/.test(err.message)) {
        console.error("[notes] server token rejected — register its sha256 in private.settings");
        return NextResponse.json({ error: "Shared notes aren't switched on yet — your draft is saved.", mode: "demo" }, { status: 503 });
      }
    }
    console.error("[notes] post failed", err);
    return NextResponse.json({ error: "Couldn't pin that right now. Your draft is saved — try again." }, { status: 502 });
  }
}
