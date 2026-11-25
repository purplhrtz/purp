import * as THREE from "three";
import { products, tracks, formatPrice } from "@content/catalog";
import type { Tab } from "@/state/store";

/** A recognisable, low-detail rendering of the storefront for the physical laptop display. */
const W = 1024, H = 652;
const covers = new Map<string, HTMLImageElement>();
function cover(src: string, onload: () => void) {
  let im = covers.get(src);
  if (!im) {
    im = new Image();
    im.src = src.replace(".jpg", "-sm.jpg");
    im.onload = onload;
    covers.set(src, im);
  }
  return im.complete && im.naturalWidth ? im : null;
}

export function createScreen() {
  const canvas = document.createElement("canvas");
  canvas.width = W;
  canvas.height = H;
  const tex = new THREE.CanvasTexture(canvas);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.anisotropy = 4;
  let last = "";
  const draw = (awake: boolean, tab: Tab, cartCount: number, force = false) => {
    const key = `${awake}|${tab}|${cartCount}`;
    if (key === last && !force) return;
    last = key;
    const g = canvas.getContext("2d")!;
    g.fillStyle = "#0b0a0d";
    g.fillRect(0, 0, W, H);
    if (!awake) {
      g.fillStyle = "#16131a";
      g.font = "500 22px 'IBM Plex Mono', monospace";
      g.fillText("purplhrtz — tap to wake", 40, H - 40);
      tex.needsUpdate = true;
      return;
    }
    const grad = g.createLinearGradient(0, 0, 0, H);
    grad.addColorStop(0, "#16121b");
    grad.addColorStop(1, "#0c0b0e");
    g.fillStyle = grad;
    g.fillRect(0, 0, W, H);
    g.fillStyle = "#e9e1d4";
    g.font = "64px Anton, Impact, sans-serif";
    g.fillText("purplhrtz", 40, 92);
    const navs: Tab[] = ["studio", "listen", "shop", "cart"];
    g.font = "700 26px 'Archivo Narrow', sans-serif";
    navs.forEach((n, i) => {
      const x = 520 + i * 118;
      g.fillStyle = n === tab ? "#b48cff" : "#8f8798";
      g.fillText(n === "cart" && cartCount ? `cart ${cartCount}` : n, x, 80);
      if (n === tab) g.fillRect(x, 92, 70, 4);
    });
    g.fillStyle = "#e9e1d4";
    g.font = "120px Anton, Impact, sans-serif";
    const head = { studio: "after midnight", listen: "listen", shop: "the shop", cart: "your cart" }[tab];
    g.fillText(head, 40, 250);
    const redraw = () => draw(awake, tab, cartCount, true);
    const items = tab === "listen" ? tracks.map((t) => ({ c: t.cover, l: t.title, r: t.duration })) :
      products.map((p) => ({ c: p.cover, l: p.title, r: formatPrice(p.priceCents) }));
    items.slice(0, 3).forEach((it, i) => {
      const x = 40 + i * 322, y = 300;
      const im = cover(it.c, redraw);
      g.fillStyle = "#211c26";
      g.fillRect(x, y, 290, 250);
      if (im) g.drawImage(im, 0, 60, 480, 413, x, y, 290, 250);
      g.fillStyle = "#e9e1d4";
      g.font = "700 26px 'Archivo Narrow', sans-serif";
      g.fillText(it.l, x, y + 288);
      g.fillStyle = "#b48cff";
      g.fillText(it.r, x + 290 - g.measureText(it.r).width, y + 288);
    });
    tex.needsUpdate = true;
  };
  return { tex, draw };
}
