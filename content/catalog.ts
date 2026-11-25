/**
 * purplhrtz — editable catalog.
 *
 * Everything the storefront shows lives here: studio copy, featured projects, preview tracks and
 * products. Prices are in cents and are the *trusted* source for checkout — the server never accepts
 * a price from the browser. Media paths point into /public/media (covers, audio) and
 * /private-downloads (paid files, served only after a verified purchase).
 *
 * To swap in real releases: replace the files under public/media and private-downloads, then edit
 * the entries below. `stripePriceId` is optional; when present (and Stripe is configured) checkout
 * uses that Price, otherwise it builds the line item from `priceCents`.
 */

export type Track = {
  id: string;
  title: string;
  note: string;
  duration: string;
  src: string; // public URL
  cover: string;
};

export type Product = {
  id: string;
  slug: string;
  kind: "drum kit" | "loop pack" | "preset bundle";
  title: string;
  tagline: string;
  description: string;
  details: string[];
  priceCents: number;
  currency: "usd";
  cover: string;
  preview: string; // public audio preview
  download: string; // file name inside /private-downloads
  stripePriceId?: string;
};

export type Project = {
  id: string;
  title: string;
  year: string;
  role: string;
  blurb: string;
  cover: string;
};

export const studio = {
  name: "purplhrtz",
  tagline: "independent music studio · basement, after midnight",
  intro:
    "purplhrtz is a one-room studio under a house that hums. We record late, mix loud then quiet, and make sounds for people who still read liner notes. Everything here was tracked within six metres of this desk — mostly with the cat asleep on the road case.",
  services: ["production & co-writing", "mixing", "sound design", "small-room live sessions"],
  contact: "bookings: open a note on the corkboard",
};

export const projects: Project[] = [
  {
    id: "night-shift",
    title: "night shift sessions",
    year: "2026",
    role: "live recording · mix",
    blurb: "Six bands, one room, no overdubs. Recorded between 11pm and 4am over a single month of Fridays.",
    cover: "/media/covers/night-shift.jpg",
  },
  {
    id: "tape-swap",
    title: "tape swap ep",
    year: "2025",
    role: "production",
    blurb: "Four songs built from cassettes traded at the back-room swap. Every hiss is somebody else's.",
    cover: "/media/covers/tape-swap.jpg",
  },
  {
    id: "hum",
    title: "hum (short film)",
    year: "2025",
    role: "score · sound design",
    blurb: "An eleven-minute score made almost entirely from the furnace, the duct and one detuned upright.",
    cover: "/media/covers/hum.jpg",
  },
];

export const tracks: Track[] = [
  {
    id: "low-ceiling",
    title: "low ceiling",
    note: "slow drums, room mics only",
    duration: "0:32",
    src: "/media/audio/low-ceiling.mp3",
    cover: "/media/covers/low-ceiling.jpg",
  },
  {
    id: "barrys-4am",
    title: "barry's 4am",
    note: "rhodes-ish keys, a purr in the left channel",
    duration: "0:32",
    src: "/media/audio/barrys-4am.mp3",
    cover: "/media/covers/barrys-4am.jpg",
  },
  {
    id: "cinder",
    title: "cinder (demo)",
    note: "sub, tape echo, painted block walls",
    duration: "0:32",
    src: "/media/audio/cinder.mp3",
    cover: "/media/covers/cinder.jpg",
  },
];

export const products: Product[] = [
  {
    id: "basement-drums-1",
    slug: "basement-drums-vol-1",
    kind: "drum kit",
    title: "basement drums vol. 1",
    tagline: "120 one-shots from a concrete room",
    description:
      "Kicks through a blanket, snares off the cinder block, hats recorded with the duct running. Dry and room versions of every hit, trimmed and tuned.",
    details: ["120 one-shots · 24-bit wav", "dry + room mic versions", "kicks tuned & labelled by note", "royalty-free for releases"],
    priceCents: 2900,
    currency: "usd",
    cover: "/media/covers/basement-drums.jpg",
    preview: "/media/audio/preview-drums.mp3",
    download: "purplhrtz-basement-drums-vol-1.zip",
    stripePriceId: undefined,
  },
  {
    id: "after-midnight-loops",
    slug: "after-midnight-loops",
    kind: "loop pack",
    title: "after midnight loops",
    tagline: "48 loops · 80–140 bpm · stems included",
    description:
      "Late-session keys, bass and tape-warped textures, cut into loops that sit under a vocal without fighting it. Key and tempo in every file name.",
    details: ["48 loops + stems", "80–140 bpm, key-labelled", "tape & no-tape versions", "royalty-free for releases"],
    priceCents: 2400,
    currency: "usd",
    cover: "/media/covers/after-midnight.jpg",
    preview: "/media/audio/preview-loops.mp3",
    download: "purplhrtz-after-midnight-loops.zip",
    stripePriceId: undefined,
  },
  {
    id: "bruised-plum-presets",
    slug: "bruised-plum-presets",
    kind: "preset bundle",
    title: "bruised plum presets",
    tagline: "64 wavetable patches + 12 multisamples",
    description:
      "Dark pads, detuned leads and a handful of basses that behave. Built for wavetable synths, with multisampled versions for any sampler.",
    details: ["64 wavetable patches", "12 multisampled instruments", "macro-mapped: tape, dust, hum", "royalty-free for releases"],
    priceCents: 1900,
    currency: "usd",
    cover: "/media/covers/bruised-plum.jpg",
    preview: "/media/audio/preview-presets.mp3",
    download: "purplhrtz-bruised-plum-presets.zip",
    stripePriceId: undefined,
  },
];

export const productById = (id: string) => products.find((p) => p.id === id);

export const formatPrice = (cents: number, currency = "usd") =>
  new Intl.NumberFormat("en-US", { style: "currency", currency: currency.toUpperCase() }).format(cents / 100);
