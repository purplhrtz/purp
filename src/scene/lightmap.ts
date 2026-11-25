import * as THREE from "three";

export type LightmapInfo = {
  scale: Record<"lamp" | "violet" | "screen" | "ambient", number>;
  colors: Record<"lamp" | "violet" | "screen" | "ambient", [number, number, number]>;
};

/** Live weights for each baked light group. Colours/scales come from public/models/lightmap.json. */
export function makeLightmapUniforms(rgb: THREE.Texture, amb: THREE.Texture) {
  return {
    lmRGB: { value: rgb },
    lmAmb: { value: amb },
    lmLamp: { value: new THREE.Color(0, 0, 0) },
    lmViolet: { value: new THREE.Color(0, 0, 0) },
    lmScreen: { value: new THREE.Color(0, 0, 0) },
    lmAmbient: { value: new THREE.Color(0, 0, 0) },
    lmLift: { value: 0.0 },
  };
}
export type LightmapUniforms = ReturnType<typeof makeLightmapUniforms>;

export function setGroup(target: THREE.Color, info: LightmapInfo, group: keyof LightmapInfo["scale"], weight: number) {
  const c = info.colors[group];
  const mean = (c[0] + c[1] + c[2]) / 3 || 1;
  // bakes stored luminance; re-apply the light's chroma without changing its brightness
  target.setRGB((c[0] / mean) * info.scale[group] * weight, (c[1] / mean) * info.scale[group] * weight, (c[2] / mean) * info.scale[group] * weight);
}

/**
 * Diffuse light comes entirely from the baked light groups (direct + bounce, from Cycles).
 * Real-time lights still add specular, so the gear and desk edge glint, and the room reflections
 * come from a cube capture of the room itself.
 */
export function patchLightmapped(mat: THREE.MeshStandardMaterial, u: LightmapUniforms) {
  mat.onBeforeCompile = (shader) => {
    Object.assign(shader.uniforms, u);
    shader.vertexShader = shader.vertexShader
      .replace("#include <common>", "#include <common>\n#ifndef USE_UV1\nattribute vec2 uv1;\n#endif\nvarying vec2 vLmUv;")
      .replace("#include <uv_vertex>", "#include <uv_vertex>\n\tvLmUv = uv1;");
    shader.fragmentShader = shader.fragmentShader
      .replace(
        "#include <common>",
        `#include <common>
uniform sampler2D lmRGB; uniform sampler2D lmAmb;
uniform vec3 lmLamp; uniform vec3 lmViolet; uniform vec3 lmScreen; uniform vec3 lmAmbient; uniform float lmLift;
varying vec2 vLmUv;`,
      )
      .replace(
        "#include <lights_fragment_maps>",
        `#include <lights_fragment_maps>
#if defined( RE_IndirectDiffuse )
	vec3 lmS = texture2D( lmRGB, vLmUv ).rgb; lmS *= lmS;
	float lmA = texture2D( lmAmb, vLmUv ).r; lmA *= lmA;
	irradiance = PI * ( lmS.r * lmLamp + lmS.g * lmViolet + lmS.b * lmScreen + lmA * lmAmbient + vec3( lmLift ) );
	iblIrradiance = vec3( 0.0 );
#endif`,
      )
      .replace("#include <lights_fragment_end>", "#include <lights_fragment_end>\n\treflectedLight.directDiffuse = vec3( 0.0 );");
  };
  mat.customProgramCacheKey = () => "purplhrtz-lightmap-v1";
  mat.needsUpdate = true;
}
