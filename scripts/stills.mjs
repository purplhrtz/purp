// Convert the Blender stills into web formats: node scripts/stills.mjs
import sharp from "sharp";
import fs from "node:fs";
for (const name of ["overview", "overview_portrait"]) {
  const src = `public/stills/${name}.jpg`;
  if (!fs.existsSync(src)) continue;
  await sharp(src).webp({ quality: 80 }).toFile(`public/stills/${name}.webp`);
  console.log(name, (fs.statSync(`public/stills/${name}.webp`).size / 1024).toFixed(0) + "KB");
}
