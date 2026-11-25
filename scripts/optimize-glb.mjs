// Compress the raw Blender exports for the web.
//   node scripts/optimize-glb.mjs
// public/models/{studio,barry}.raw.glb -> public/models/{studio,barry}.glb  (meshopt + WebP)
// public/models/lightmap.png           -> public/models/lightmap.webp (+ lightmap-1k.webp for phones)
import { NodeIO } from "@gltf-transform/core";
import { ALL_EXTENSIONS } from "@gltf-transform/extensions";
import { dedup, prune, weld, meshopt, textureCompress, quantize } from "@gltf-transform/functions";
import { MeshoptEncoder, MeshoptDecoder } from "meshoptimizer";
import sharp from "sharp";
import fs from "node:fs/promises";
import path from "node:path";

const dir = path.resolve("public/models");
await MeshoptEncoder.ready;
await MeshoptDecoder.ready;
const io = new NodeIO()
  .registerExtensions(ALL_EXTENSIONS)
  .registerDependencies({ "meshopt.encoder": MeshoptEncoder, "meshopt.decoder": MeshoptDecoder });

// Decals carry readable type, keep them sharper than tiling materials.
const SHARP = /(flyer|tape|rack_faces|midi_top|albedo_Barry|Barry_)/i;

async function optimize(name) {
  const src = path.join(dir, `${name}.raw.glb`);
  const doc = await io.read(src);
  // per-texture resize: decals 1024, everything else 512 (lighting comes from the lightmap)
  for (const tex of doc.getRoot().listTextures()) {
    const label = `${tex.getName()} ${tex.getURI()}`;
    const max = SHARP.test(label) ? 1024 : 512;
    const img = tex.getImage();
    if (!img) continue;
    const out = await sharp(Buffer.from(img)).resize(max, max, { fit: "inside", withoutEnlargement: true })
      .webp({ quality: /normal/i.test(label) ? 88 : 82 }).toBuffer();
    tex.setImage(new Uint8Array(out)).setMimeType("image/webp");
  }
  // Barry is animated per-node, so keep his transforms un-normalised (no quantize)
  await doc.transform(dedup(), prune({ keepAttributes: true, keepLeaves: true }), weld({ tolerance: 0.00005 }),
    ...(name === "barry" ? [] : [quantize({ quantizeTexcoord: 14 })]),
    meshopt({ encoder: MeshoptEncoder, level: "medium" }));
  doc.createExtension(ALL_EXTENSIONS.find((e) => e.EXTENSION_NAME === "EXT_texture_webp")).setRequired(true);
  const dst = path.join(dir, `${name}.glb`);
  await io.write(dst, doc);
  const [a, b] = await Promise.all([fs.stat(src), fs.stat(dst)]);
  console.log(`${name}: ${(a.size / 1e6).toFixed(2)}MB -> ${(b.size / 1e6).toFixed(2)}MB`);
}

await optimize("studio");
await optimize("barry");

// Lightmap: RGBA png -> two alpha-free WebPs (browsers premultiply alpha on decode, which would
// wreck the RGB channels wherever ambient is dark). lm-rgb = lamp/violet/screen, lm-amb = ambient.
const lm = path.join(dir, "lightmap.png");
const outs = [];
for (const [suffix, size] of [["", 2048], ["-1k", 1024]]) {
  const rgb = `lightmap-rgb${suffix}.webp`;
  const amb = `lightmap-amb${suffix}.webp`;
  await sharp(lm).resize(size, size).removeAlpha().webp({ quality: 92 }).toFile(path.join(dir, rgb));
  await sharp(lm).resize(size / 2, size / 2).extractChannel(3).webp({ quality: 90 }).toFile(path.join(dir, amb));
  outs.push(rgb, amb);
}
for (const f of outs) console.log(f, ((await fs.stat(path.join(dir, f))).size / 1e6).toFixed(2) + "MB");
