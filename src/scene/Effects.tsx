"use client";
import { EffectComposer, Bloom, Vignette } from "@react-three/postprocessing";

/** Halation around the practicals + a gentle vignette. Grain is a CSS layer (shared with the still). */
export function Effects({ tier }: { tier: "low" | "mid" | "high" }) {
  if (tier === "low") return null;
  return (
    <EffectComposer multisampling={tier === "high" ? 4 : 0}>
      <Bloom mipmapBlur intensity={tier === "high" ? 0.85 : 0.6} luminanceThreshold={0.72} luminanceSmoothing={0.25} radius={0.78} />
      <Vignette offset={0.32} darkness={0.62} />
    </EffectComposer>
  );
}
