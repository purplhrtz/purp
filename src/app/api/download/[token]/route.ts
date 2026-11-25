import fs from "node:fs/promises";
import path from "node:path";
import { productById } from "@content/catalog";
import { modes } from "@/lib/server/env";
import { stripe } from "@/lib/server/stripe";
import { findOrder, productIdsFromSession } from "@/lib/server/orders";
import { verifyDownload } from "@/lib/server/tokens";

export const runtime = "nodejs";

export async function GET(_req: Request, ctx: { params: Promise<{ token: string }> }) {
  const { token } = await ctx.params;
  const claim = verifyDownload(token);
  if (!claim) return new Response("This download link is invalid or has expired.", { status: 403 });
  const product = productById(claim.p);
  if (!product) return new Response("Not found", { status: 404 });

  // Belt and braces: the order must be on record, or Stripe must confirm the session is paid.
  let owned = (await findOrder(claim.s).catch(() => null))?.includes(product.id) ?? false;
  if (!owned && modes().checkout === "stripe") {
    const s = await stripe().checkout.sessions.retrieve(claim.s).catch(() => null);
    owned = !!s && s.payment_status === "paid" && productIdsFromSession(s).includes(product.id);
  }
  if (!owned) return new Response("No paid order found for this download.", { status: 403 });

  const file = path.join(process.cwd(), "private-downloads", path.basename(product.download));
  try {
    const data = await fs.readFile(file);
    return new Response(new Uint8Array(data), {
      headers: {
        "Content-Type": "application/zip",
        "Content-Disposition": `attachment; filename="${path.basename(product.download)}"`,
        "Cache-Control": "private, no-store",
      },
    });
  } catch {
    return new Response("File missing — the studio has been told.", { status: 500 });
  }
}
