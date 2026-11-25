# purplhrtz

A landing page for an independent music studio that takes place inside a basement recording studio after
midnight. Visitors move a camera around the room, meet Barry (the orange tabby), and use the laptop on the
desk as the actual website: listen to previews, browse kits/loops/presets, check out with Stripe, and pin a
note to the corkboard.

Next.js (App Router) · TypeScript · React Three Fiber · Blender (headless `bpy`) · Stripe Checkout · Supabase

```bash
npm install
cp .env.example .env.local   # optional — everything has a labelled demo fallback
npm run dev                   # http://localhost:3000
```

## How it fits together

| Layer | Where |
| --- | --- |
| Editable catalog, tracks, projects, studio copy | `content/catalog.ts` |
| Product sleeves / track covers | `public/media/covers/*.jpg` (+ `-sm.jpg` thumbnails) |
| Track and product previews | `public/media/audio/*.mp3` |
| Sound effects (room tone, lamp, startup, purrs) | `public/media/sfx/*.mp3` |
| Paid downloads (never public) | `private-downloads/*.zip` |
| 3D room + Barry | `public/models/studio.glb`, `barry.glb`, `lightmap-*.webp`, `lightmap.json` |
| Loading / fallback stills | `public/stills/overview*.{jpg,webp}` |
| Scene code | `src/scene/*` (room, lightmap shader, camera rig, Barry, dust, effects) |
| UI | `src/ui/*` (dock controls, laptop storefront, corkboard guestbook) |
| Server routes | `src/app/api/*` (checkout, verify, webhook, download, notes) |
| Database schema | `supabase/migrations/*.sql` |

**First paint is the art-directed still** (rendered in Blender from the same camera as the 3D opening), with
working controls. The WebGL room loads progressively and cross-fades in on its first frame. Without WebGL — or
if the models fail to load — the still stays up with labelled hotspots, and the laptop and corkboard work the
same way.

**Lighting** is baked in Cycles into four light groups (lamp, violet strip, laptop screen, ambient spill)
packed into two WebP lightmaps. At runtime a small shader patch recombines them with live weights, so the lamp
switch, the laptop waking up and the music-driven violet breathing all relight the room's materials (bounce
light included) at the cost of two texture reads. Real-time lights only add specular glints and light Barry.

## Replacing content

- **Catalog**: edit `content/catalog.ts`. Prices are in cents and are the *only* prices the server trusts.
  Add `stripePriceId` to a product to bill an existing Stripe Price instead of the catalog amount.
- **Artwork**: drop a real photo/sleeve at the same path (1200×1200 + a 480×480 `-sm.jpg`), or regenerate the
  provisional ones with `npm run assets:covers`.
- **Audio**: replace the mp3s in `public/media/audio` (keep the file names or update `catalog.ts`). The
  provisional tracks/sfx are synthesized by `npm run assets:audio`.
- **Downloads**: replace the zips in `private-downloads/` (file names are referenced by `download` in the catalog).
- **Models**: the Blender pipeline is `blender/build_studio.py` (stages: `build`, `bake`, `render`, `export`).
  It needs the `bpy` package (Blender as a Python module):
  ```bash
  python3 -m venv /opt/bpyenv && /opt/bpyenv/bin/pip install bpy numpy pillow
  npm run assets:textures      # procedural PBR textures, flyers, tape labels
  npm run assets:blender       # build -> bake lightmaps -> render stills -> export GLBs (CPU: ~30–40 min)
  npm run assets:glb           # meshopt + WebP compression, lightmap packing
  npm run assets:stills        # still JPG -> WebP
  ```
  To swap in a supplied Barry, export a rigged cat to `public/models/barry.glb` with nodes named
  `Barry_Body`, `Barry_Head`, `Barry_EarL/R`, `Barry_EyeL/R`, `Barry_Tail` (or adapt `src/scene/Barry.tsx` to
  play the rig's own idle clips via `useAnimations`).

## Enabling live checkout (Stripe)

1. Put a secret key in `STRIPE_SECRET_KEY` (`sk_test_…` for a sandbox). Without it the cart runs a clearly
   labelled demo checkout that collects no payment details.
2. Create a webhook endpoint at `https://<your-domain>/api/stripe/webhook` for
   `checkout.session.completed` and `checkout.session.async_payment_succeeded`; set `STRIPE_WEBHOOK_SECRET`.
3. Set `DOWNLOAD_SIGNING_SECRET` (any long random string) and `NEXT_PUBLIC_SITE_URL`.
4. If you collect sales tax/VAT, enable Stripe Tax and add `automatic_tax` in `src/app/api/checkout/route.ts`.

Flow: the server builds a hosted Checkout Session from catalog prices → Stripe redirects back to
`/?checkout=success&session_id=…` → `/api/checkout/verify` re-reads the session from Stripe and only if it is
`paid` records the order and returns signed, expiring download links. The webhook records the same order
idempotently (repeat deliveries of an event are acknowledged and ignored). `/api/download/[token]` checks the
signature, expiry and the recorded order (or Stripe) before streaming the file.

## Enabling shared notes (Supabase)

1. Apply `supabase/migrations/20261125000000_guestbook_and_orders.sql`.
2. Generate a server token and register **only its SHA-256** in the database:
   ```bash
   TOKEN=$(openssl rand -hex 32); echo "SUPABASE_SERVER_RPC_TOKEN=$TOKEN" >> .env.local
   printf %s "$TOKEN" | sha256sum   # paste the hash below
   ```
   ```sql
   insert into private.settings (key, value) values ('server_rpc_token_sha256', '<hash>')
   on conflict (key) do update set value = excluded.value;
   ```
3. Set `SUPABASE_URL`, `SUPABASE_ANON_KEY` (publishable key) and `NOTES_IP_SALT`.

Tables are locked behind RLS with no client policies. The server validates notes (length, control characters,
honeypot), rate-limits per hashed IP in memory, and calls `SECURITY DEFINER` functions that check the token,
re-validate, and enforce a per-IP (3 / 10 min) and global (30 / min) limit. Notes render as plain text. Without
Supabase, notes are kept on the visitor's device and labelled as such.

## Local development behind an HTTPS proxy

Node's built-in `fetch` ignores `HTTPS_PROXY` unless started with `NODE_USE_ENV_PROXY=1` (Node ≥ 22.21).
The Stripe client uses `fetch`, so `NODE_USE_ENV_PROXY=1 npm run dev` is enough.
