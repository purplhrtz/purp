import type { Metadata, Viewport } from "next";
import "@fontsource/anton/400.css";
import "@fontsource/archivo-narrow/500.css";
import "@fontsource/archivo-narrow/700.css";
import "@fontsource/ibm-plex-mono/500.css";
import "./globals.css";

const site = process.env.NEXT_PUBLIC_SITE_URL || (process.env.VERCEL_URL ? `https://${process.env.VERCEL_URL}` : "http://localhost:3000");

export const metadata: Metadata = {
  metadataBase: new URL(site),
  title: "purplhrtz — independent music studio",
  description: "A basement recording studio after midnight. Listen, shop kits and loops, and leave a note on the corkboard.",
  openGraph: { title: "purplhrtz", description: "independent music studio · basement, after midnight", images: ["/stills/overview.jpg"] },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  themeColor: "#0a090c",
  interactiveWidget: "resizes-content",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <link rel="preload" as="image" href="/stills/overview.webp" media="(min-aspect-ratio: 17/20)" />
        <link rel="preload" as="image" href="/stills/overview_portrait.webp" media="(max-aspect-ratio: 17/20)" />
      </head>
      <body>{children}</body>
    </html>
  );
}
