"""purplhrtz basement studio — headless Blender build.

Stages (run all by default):
  build   -> model room/props/Barry, materials, lights, cameras; save blender/cache/studio.blend
  bake    -> bake packed light-group lightmap (R lamp, G violet, B screen, A ambient)
  render  -> Cycles stills for loading/fallback (landscape + portrait, lamp on)
  export  -> public/models/studio.glb + barry.glb (unoptimized; scripts/optimize-glb.mjs compresses)

Usage:
  /opt/bpyenv/bin/python blender/build_studio.py [build|bake|render|export|all] [--quick]

Coordinates: Blender Z-up metres. Room interior X[-2.6,2.6] Y[0,6.2] Z[0,2.45].
The camera starts at the foot of the stairs (stairwell behind the Y=0 wall, right side).
"""
from __future__ import annotations

import math
import os
import random
import sys

import bpy  # must come first: the pip bpy module provides bmesh/mathutils
import bmesh
import numpy as np
from mathutils import Euler, Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
TEX = os.path.join(HERE, "textures")
CACHE = os.path.join(HERE, "cache")
OUT_MODELS = os.path.join(REPO, "public", "models")
OUT_STILLS = os.path.join(REPO, "public", "stills")
os.makedirs(CACHE, exist_ok=True)
os.makedirs(OUT_MODELS, exist_ok=True)
os.makedirs(OUT_STILLS, exist_ok=True)
BLEND = os.path.join(CACHE, "studio.blend")

ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
STAGE = ARGS[0] if ARGS else "all"
QUICK = "--quick" in sys.argv
random.seed(7)

W0, W1 = -2.6, 2.6     # room x
D0, D1 = 0.0, 6.2      # room y
H = 2.45               # ceiling
JAMB_X = 1.5           # doorway inner edge (stairwell spans JAMB_X..W1)
F = 1.0                # front wall (stairs) y position

# ---------------------------------------------------------------- shots (shared with the web app)
# position, look-at target, vertical fov (deg). Converted to three.js (x, z, -y) in src/scene/shots.ts
SHOTS = {
    "overview": ((2.04, 0.56, 1.55), (-0.1, 5.6, 0.84), 38.0),
    "overview_portrait": ((1.92, 0.6, 1.45), (0.58, 5.6, 0.95), 60.0),
}


def kelvin_rgb(k: float):
    t = k / 100.0
    if t <= 66:
        r = 1.0
        g = max(0, min(1, (99.4708025861 * math.log(t) - 161.1195681661) / 255))
        b = 0 if t <= 19 else max(0, min(1, (138.5177312231 * math.log(t - 10) - 305.0447927307) / 255))
    else:
        r = max(0, min(1, 329.698727446 * ((t - 60) ** -0.1332047592) / 255))
        g = max(0, min(1, 288.1221695283 * ((t - 60) ** -0.0755148492) / 255))
        b = 1.0
    # to linear
    return tuple(c ** 2.2 for c in (r, g, b))


LAMP_RGB = kelvin_rgb(2600)
VIOLET_RGB = (0.42, 0.12, 1.0)
SCREEN_RGB = (0.62, 0.66, 1.0)
STAIR_RGB = kelvin_rgb(3000)


# ================================================================ utilities
def clear_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def coll(name):
    c = bpy.data.collections.get(name)
    if not c:
        c = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(c)
    return c


def link(obj, collection):
    for c in obj.users_collection:
        c.objects.unlink(obj)
    coll(collection).objects.link(obj)
    return obj


def img(path, colorspace="sRGB"):
    name = os.path.basename(path)
    im = bpy.data.images.get(name)
    if im is None:
        im = bpy.data.images.load(path)
        im.colorspace_settings.name = colorspace
    return im


def material(name, tex=None, color=(0.5, 0.5, 0.5), rough=0.7, metal=0.0, tile=1.0, normal=1.0,
             emission=None, estrength=0.0, sheen=0.0, coat=0.0, decal=None, alpha=None):
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m["tile"] = tile
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (-300, 0)
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metal
    bsdf.inputs["Base Color"].default_value = (*color, 1)
    if sheen:
        bsdf.inputs["Sheen Weight"].default_value = sheen
    if coat:
        bsdf.inputs["Coat Weight"].default_value = coat
    base = decal or tex
    if base:
        p = os.path.join(TEX, f"{base}_albedo.png") if not base.endswith(".png") else os.path.join(TEX, base)
        t = nt.nodes.new("ShaderNodeTexImage")
        t.image = img(p)
        t.location = (-700, 200)
        if decal:
            t.extension = "CLIP"
        nt.links.new(t.outputs["Color"], bsdf.inputs["Base Color"])
    if tex:
        rp = os.path.join(TEX, f"{tex}_rough.png")
        if os.path.exists(rp):
            tr = nt.nodes.new("ShaderNodeTexImage")
            tr.image = img(rp, "Non-Color")
            tr.location = (-700, -100)
            nt.links.new(tr.outputs["Color"], bsdf.inputs["Roughness"])
        npth = os.path.join(TEX, f"{tex}_normal.png")
        if os.path.exists(npth) and normal > 0:
            tn = nt.nodes.new("ShaderNodeTexImage")
            tn.image = img(npth, "Non-Color")
            tn.location = (-900, -400)
            nm = nt.nodes.new("ShaderNodeNormalMap")
            nm.inputs["Strength"].default_value = normal
            nm.location = (-500, -400)
            nt.links.new(tn.outputs["Color"], nm.inputs["Color"])
            nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
    if emission is not None:
        bsdf.inputs["Emission Color"].default_value = (*emission, 1)
        bsdf.inputs["Emission Strength"].default_value = estrength
    return m


def new_obj(name, bm, mat, collection="STATIC", mats=None):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    coll(collection).objects.link(ob)
    for m in (mats or [mat]):
        if m:
            me.materials.append(m)
    return ob


def box(name, x0, x1, y0, y1, z0, z1, mat, bevel=0.0, collection="STATIC", segs=2):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.x = x0 + (v.co.x + 0.5) * (x1 - x0)
        v.co.y = y0 + (v.co.y + 0.5) * (y1 - y0)
        v.co.z = z0 + (v.co.z + 0.5) * (z1 - z0)
    if bevel > 0:
        bmesh.ops.bevel(bm, geom=list(bm.edges), offset=bevel, segments=segs, affect="EDGES", profile=0.5)
    return new_obj(name, bm, mat, collection)


def cyl(name, center, radius, depth, mat, axis="Z", segs=24, r2=None, collection="STATIC", cap=True, bevel=0.0):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=cap, cap_tris=False, segments=segs, radius1=radius,
                          radius2=radius if r2 is None else r2, depth=depth)
    if bevel:
        bmesh.ops.bevel(bm, geom=[e for e in bm.edges if len(e.link_faces) == 2 and
                                  abs(e.link_faces[0].normal.dot(e.link_faces[1].normal)) < 0.5],
                        offset=bevel, segments=2, affect="EDGES", profile=0.5)
    rot = {"Z": Matrix(), "X": Matrix.Rotation(math.pi / 2, 4, "Y"), "Y": Matrix.Rotation(math.pi / 2, 4, "X")}[axis]
    bmesh.ops.transform(bm, matrix=Matrix.Translation(Vector(center)) @ rot, verts=bm.verts)
    return new_obj(name, bm, mat, collection)


def sphere(name, center, radius, mat, scale=(1, 1, 1), segs=24, rings=12, collection="STATIC"):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=segs, v_segments=rings, radius=radius)
    bmesh.ops.scale(bm, vec=Vector(scale), verts=bm.verts)
    bmesh.ops.translate(bm, vec=Vector(center), verts=bm.verts)
    return new_obj(name, bm, mat, collection)


def plane(name, corners, mat, collection="STATIC", uv=None, subdiv=0):
    bm = bmesh.new()
    vs = [bm.verts.new(Vector(c)) for c in corners]
    f = bm.faces.new(vs)
    if uv:
        lay = bm.loops.layers.uv.new("UVMap")
        for loop, u in zip(f.loops, uv):
            loop[lay].uv = u
    if subdiv:
        bmesh.ops.subdivide_edges(bm, edges=list(bm.edges), cuts=subdiv, use_grid_fill=True)
    return new_obj(name, bm, mat, collection)


def tube(name, points, radius, mat, collection="STATIC", res=8):
    cu = bpy.data.curves.new(name + "_c", "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = radius
    cu.bevel_resolution = 2
    cu.resolution_u = res
    sp = cu.splines.new("BEZIER")
    sp.bezier_points.add(len(points) - 1)
    for bp, p in zip(sp.bezier_points, points):
        bp.co = Vector(p)
        bp.handle_left_type = bp.handle_right_type = "AUTO"
    ob = bpy.data.objects.new(name, cu)
    coll(collection).objects.link(ob)
    if mat:
        cu.materials.append(mat)
    return to_mesh(ob)


def to_mesh(ob):
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    me = bpy.data.meshes.new_from_object(ev)
    new = bpy.data.objects.new(ob.name, me)
    for c in ob.users_collection:
        c.objects.link(new)
    new.matrix_world = ob.matrix_world.copy()
    name = ob.name
    bpy.data.objects.remove(ob)
    new.name = name
    return new


def bend(ob, axis_origin, angle, axis="Z", deform_axis="Z"):
    """Simple-deform bend (applied) — used for curling flyers."""
    emp = bpy.data.objects.new(ob.name + "_bend", None)
    bpy.context.scene.collection.objects.link(emp)
    emp.location = axis_origin
    mod = ob.modifiers.new("bend", "SIMPLE_DEFORM")
    mod.deform_method = "BEND"
    mod.angle = angle
    mod.origin = emp
    mod.deform_axis = deform_axis
    apply_mods(ob)
    bpy.data.objects.remove(emp)


def apply_mods(ob):
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    me = bpy.data.meshes.new_from_object(ev)
    old = ob.data
    ob.modifiers.clear()
    ob.data = me
    bpy.data.meshes.remove(old)


def subsurf(ob, levels=2):
    m = ob.modifiers.new("ss", "SUBSURF")
    m.levels = m.render_levels = levels
    apply_mods(ob)


def smooth(ob, angle=40):
    for p in ob.data.polygons:
        p.use_smooth = True
    try:
        ob.data.set_sharp_from_angle(angle=math.radians(angle))
    except Exception:
        pass


def box_uv(ob):
    """World-space triplanar box mapping into the 'UVMap' layer, scaled per material 'tile' (metres)."""
    me = ob.data
    if not me.uv_layers:
        me.uv_layers.new(name="UVMap")
    uv = me.uv_layers[0].data
    mw = ob.matrix_world
    nmat = mw.to_3x3().inverted().transposed()
    for p in me.polygons:
        m = me.materials[p.material_index] if me.materials else None
        tile = float(m.get("tile", 1.0)) if m else 1.0
        n = (nmat @ p.normal).normalized()
        ax = max(range(3), key=lambda i: abs(n[i]))
        for li in p.loop_indices:
            co = mw @ me.vertices[me.loops[li].vertex_index].co
            if ax == 0:
                u, v = co.y * (1 if n.x > 0 else -1), co.z
            elif ax == 1:
                u, v = co.x * (-1 if n.y > 0 else 1), co.z
            else:
                u, v = co.x, co.y
            uv[li].uv = (u / tile, v / tile)


def decal_uv(ob):
    """Planar 0..1 UVs from the object's own bounding rectangle (for flyers/labels/screens)."""
    me = ob.data
    if not me.uv_layers:
        me.uv_layers.new(name="UVMap")
    uv = me.uv_layers[0].data
    co = np.array([v.co[:] for v in me.vertices])
    ext = co.max(0) - co.min(0)
    a, b = sorted(range(3), key=lambda i: -ext[i])[:2]
    # prefer horizontal axis as u
    if a == 2:
        a, b = b, a
    lo, hi = co.min(0), co.max(0)
    for li, loop in enumerate(me.loops):
        c = me.vertices[loop.vertex_index].co
        uv[li].uv = ((c[a] - lo[a]) / max(hi[a] - lo[a], 1e-6), (c[b] - lo[b]) / max(hi[b] - lo[b], 1e-6))


# ================================================================ materials
def build_materials():
    M = {}
    M["concrete"] = material("concrete", "concrete", rough=0.8, tile=2.2, normal=0.6)
    M["cinder"] = material("cinder", "cinder", rough=0.85, tile=0.8, normal=1.0)
    M["ceiling"] = material("ceiling", "stairs", color=(0.05, 0.05, 0.05), rough=0.9, tile=1.2, normal=0.4)
    M["acoustic"] = material("acoustic", "acoustic", rough=0.95, tile=0.6, sheen=0.3)
    M["acoustic_plum"] = material("acoustic_plum", "acoustic_plum", rough=0.95, tile=0.6, sheen=0.3)
    M["desk"] = material("desk", "desk", rough=0.5, tile=1.4, coat=0.15)
    M["desk_edge"] = material("desk_edge", "stairs", rough=0.65, tile=0.5)
    M["stairs"] = material("stairs", "stairs", rough=0.7, tile=1.0)
    M["rack"] = material("rack", "rack", rough=0.45, metal=0.6, tile=0.5)
    M["steel"] = material("steel", "steel", rough=0.4, metal=0.9, tile=0.6)
    M["cork"] = material("cork", "cork", rough=0.9, tile=0.5)
    M["rug"] = material("rug", "rug", rough=0.97, tile=2.6)
    M["couch"] = material("couch", "couch", rough=0.55, tile=0.7, coat=0.1)
    M["blanket"] = material("blanket", "blanket", rough=0.95, tile=0.35, sheen=0.5)
    M["plastic_black"] = material("plastic_black", "plastic_black", rough=0.45, tile=0.3)
    M["plastic_grey"] = material("plastic_grey", "plastic_grey", rough=0.5, tile=0.3)
    M["rubber"] = material("rubber", color=(0.02, 0.02, 0.022), rough=0.75)
    M["woofer"] = material("woofer", color=(0.03, 0.03, 0.035), rough=0.65)
    M["key_white"] = material("key_white", color=(0.62, 0.6, 0.56), rough=0.35)
    M["key_black"] = material("key_black", color=(0.015, 0.015, 0.018), rough=0.3)
    M["laptop"] = material("laptop", color=(0.16, 0.16, 0.17), rough=0.35, metal=0.85)
    M["laptop_key"] = material("laptop_key", color=(0.02, 0.02, 0.022), rough=0.6)
    M["paint_trim"] = material("paint_trim", "stairs", color=(0.25, 0.23, 0.24), rough=0.6, tile=0.9)
    M["duct"] = material("duct", "steel", rough=0.35, metal=1.0, tile=1.5)
    M["cable"] = material("cable", color=(0.01, 0.01, 0.012), rough=0.5)
    M["mug"] = material("mug", color=(0.5, 0.47, 0.42), rough=0.25)
    M["roadcase"] = material("roadcase", "plastic_black", color=(0.04, 0.04, 0.045), rough=0.55, tile=0.4)
    M["lampshade"] = material("lampshade", "lampshade", rough=0.35, metal=0.5, tile=0.2)
    M["tape_purplhrtz"] = material("tape_purplhrtz", decal="tape_purplhrtz", rough=0.8)
    M["tape_labels"] = material("tape_labels", decal="tape_labels", rough=0.8)
    M["rack_faces"] = material("rack_faces", decal="rack_faces", rough=0.45, metal=0.3)
    M["midi_top"] = material("midi_top", decal="midi_top", rough=0.5)
    for f in ("flyer_a", "flyer_b", "flyer_c"):
        M[f] = material(f, decal=f, rough=0.85)
    M["paper"] = material("paper", color=(0.72, 0.68, 0.6), rough=0.9)
    M["paper_violet"] = material("paper_violet", color=(0.55, 0.45, 0.65), rough=0.9)
    M["pin"] = material("pin", color=(0.5, 0.08, 0.3), rough=0.3)
    # emissive / dynamic
    M["bulb"] = material("bulb", color=(1, 0.9, 0.7), emission=LAMP_RGB, estrength=40.0, rough=0.2)
    M["violet_led"] = material("violet_led", color=(0.4, 0.1, 1), emission=VIOLET_RGB, estrength=10.0)
    M["screen"] = material("screen", color=(0.002, 0.002, 0.003), emission=SCREEN_RGB, estrength=0.02, rough=0.1)
    M["led_amber"] = material("led_amber", color=(1, 0.5, 0.1), emission=(1, 0.45, 0.1), estrength=12)
    M["led_violet"] = material("led_violet", color=(0.5, 0.2, 1), emission=VIOLET_RGB, estrength=12)
    M["stair_glow"] = material("stair_glow", color=(1, 0.8, 0.6), emission=STAIR_RGB, estrength=6)
    return M


# ================================================================ room
def build_room(M):
    # floor / ceiling
    box("floor", W0 - 0.3, W1 + 0.3, -2.0, D1 + 0.3, -0.1, 0.0, M["concrete"])
    box("ceiling", W0 - 0.3, W1 + 0.3, F - 0.2, D1 + 0.3, H, H + 0.1, M["ceiling"])
    box("ceiling_stair_l", W0 - 0.3, JAMB_X - 0.2, F - 3.0, F - 0.2, H, H + 0.1, M["ceiling"])
    # walls (cinder block, 0.2 thick)
    box("wall_back", W0 - 0.2, W1 + 0.2, D1, D1 + 0.2, 0, H, M["cinder"])
    box("wall_left", W0 - 0.2, W0, F - 0.2, D1, 0, H, M["cinder"])
    box("wall_right", W1, W1 + 0.2, -2.0, D1, 0, H, M["cinder"])
    # front wall with doorway on the right (stairwell)
    box("wall_front", W0 - 0.2, JAMB_X, F - 0.2, F, 0, H, M["cinder"])
    box("wall_front_header", JAMB_X, W1, F - 0.2, F, 2.08, H, M["cinder"])
    # stairwell left wall
    box("stairwell_wall", JAMB_X - 0.2, JAMB_X, F - 3.0, F - 0.2, 0, H, M["cinder"])
    # door casing: painted trim on the jamb we see in the foreground
    box("jamb_liner", JAMB_X - 0.012, JAMB_X + 0.012, F - 0.22, F + 0.02, 0, 2.08, M["paint_trim"], bevel=0.004)
    box("casing_room", JAMB_X - 0.06, JAMB_X + 0.012, F, F + 0.025, 0, 2.14, M["paint_trim"], bevel=0.006)
    box("casing_head", JAMB_X - 0.06, W1, F, F + 0.025, 2.08, 2.15, M["paint_trim"], bevel=0.006)
    # stairs (behind camera, mostly for bounce + the bottom step under the camera)
    for i in range(12):
        z = 0.19 * (i + 1)
        y1 = F - 0.25 - 0.26 * i
        box(f"step_{i}", JAMB_X + 0.02, W1, y1 - 0.26, y1, 0, z, M["stairs"], bevel=0.008)
    # handrail on the right wall of the stairwell, running into the room a little
    tube("handrail", [(W1 - 0.06, F - 2.0, 2.95), (W1 - 0.06, F - 0.9, 1.85), (W1 - 0.06, F - 0.15, 1.05)], 0.024, M["stairs"])
    for y, z in ((F - 1.6, 2.5), (F - 0.5, 1.45)):
        cyl(f"rail_bracket_{y}", (W1 - 0.03, y, z - 0.03), 0.008, 0.07, M["steel"], axis="X", segs=8)
    # ceiling joists + a duct (ventilation hum)
    for i, x in enumerate(np.arange(W0 + 0.2, W1, 0.6)):
        box(f"joist_{i}", x - 0.03, x + 0.03, F - 0.2, D1, H - 0.2, H, M["ceiling"])
    box("duct", -1.9, -1.35, F - 0.2, D1, H - 0.55, H - 0.22, M["duct"], bevel=0.01)
    for y in np.arange(F + 0.4, D1, 1.2):
        box(f"duct_seam_{y:.1f}", -1.92, -1.33, y, y + 0.025, H - 0.57, H - 0.2, M["duct"])
    box("vent_grille", -1.85, -1.4, 4.6, 4.9, H - 0.58, H - 0.55, M["rack"])
    # pipe along the back wall
    cyl("pipe_back", (0, D1 - 0.08, H - 0.12), 0.025, 5.2, M["steel"], axis="X", segs=12)
    # rug
    box("rug", -1.95, 1.0, 3.9, 6.05, 0.0, 0.008, M["rug"])
    # baseboard grime strip (darker band) is in the cinder texture; add an electrical box + conduit
    box("outlet_box", 0.95, 1.07, D1 - 0.04, D1, 0.32, 0.44, M["steel"], bevel=0.004)
    cyl("conduit", (1.01, D1 - 0.03, 0.44 + 0.95), 0.012, 1.9, M["steel"], segs=10)


def build_desk(M):
    top_z = 0.76
    x0, x1, y0, y1 = -1.6, 0.8, 5.45, 6.15
    box("desk_top", x0, x1, y0 + 0.02, y1, top_z - 0.035, top_z, M["desk"], bevel=0.004)
    # worn rounded front edge
    cyl("desk_edge", ((x0 + x1) / 2, y0 + 0.025, top_z - 0.0175), 0.0185, x1 - x0, M["desk_edge"], axis="X", segs=16)
    for x in (x0 + 0.05, x1 - 0.05):
        box(f"desk_leg_{x:.2f}", x - 0.025, x + 0.025, y0 + 0.08, y1 - 0.05, 0, top_z - 0.035, M["rack"])
    box("desk_modesty", x0 + 0.05, x1 - 0.05, y1 - 0.06, y1 - 0.04, 0.25, top_z - 0.04, M["rack"])
    box("desk_shelf", x0 + 0.08, x1 - 0.08, y0 + 0.25, y1 - 0.06, 0.16, 0.18, M["desk"])
    # crate of records under desk
    box("crate", -1.35, -0.95, 5.65, 6.05, 0.18, 0.5, M["desk_edge"], bevel=0.006)
    for i in range(14):
        box(f"record_{i}", -1.33 + i * 0.026, -1.315 + i * 0.026, 5.67, 6.03, 0.19, 0.49 - (i % 3) * 0.01,
            M["paper"] if i % 4 else M["paper_violet"])

    # --- monitors on stands
    for side, mx in (("L", -1.32), ("R", 0.52)):
        cyl(f"stand_{side}", (mx, 5.98, top_z + 0.09), 0.025, 0.18, M["rack"], segs=12)
        box(f"stand_plate_{side}", mx - 0.11, mx + 0.11, 5.88, 6.08, top_z + 0.18, top_z + 0.195, M["rack"])
        bz = top_z + 0.195
        mon = box(f"monitor_{side}", mx - 0.105, mx + 0.105, 5.86, 6.12, bz, bz + 0.33, M["plastic_black"], bevel=0.012)
        cyl(f"woofer_{side}", (mx, 5.857, bz + 0.12), 0.072, 0.01, M["woofer"], axis="Y", segs=32)
        cyl(f"woofer_ring_{side}", (mx, 5.855, bz + 0.12), 0.082, 0.006, M["plastic_grey"], axis="Y", segs=32, r2=0.082)
        cyl(f"dustcap_{side}", (mx, 5.85, bz + 0.12), 0.022, 0.012, M["rubber"], axis="Y", segs=16)
        cyl(f"tweeter_{side}", (mx, 5.855, bz + 0.265), 0.022, 0.008, M["plastic_grey"], axis="Y", segs=20)
        box(f"port_{side}", mx - 0.05, mx + 0.05, 5.856, 5.858, bz + 0.025, bz + 0.045, M["rubber"])
        sphere(f"monitor_led_{side}", (mx + 0.08, 5.857, bz + 0.03), 0.004, M["led_violet"], collection="EMISSIVE")

    # --- acoustic panels + bass traps on back wall
    for i, px in enumerate((-1.55, -0.95, 0.05, 0.65)):
        mat = M["acoustic_plum"] if i in (1, 2) else M["acoustic"]
        box(f"panel_{i}", px - 0.0, px + 0.55, D1 - 0.07, D1, 1.02, 2.12, mat, bevel=0.015)
    box("panel_center", -0.38, 0.0, D1 - 0.07, D1, 1.25, 2.12, M["acoustic"], bevel=0.015)
    for i, (cx, s) in enumerate(((W0, 1), (W1, -1))):
        bm = bmesh.new()
        vs = [bm.verts.new((cx, D1, 0.0)), bm.verts.new((cx + s * 0.38, D1, 0.0)), bm.verts.new((cx, D1 - 0.38, 0.0))]
        bm.faces.new(vs if s > 0 else vs[::-1])
        ext = bmesh.ops.extrude_face_region(bm, geom=bm.faces[:])
        bmesh.ops.translate(bm, vec=(0, 0, 2.2), verts=[v for v in ext["geom"] if isinstance(v, bmesh.types.BMVert)])
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        new_obj(f"basstrap_{i}", bm, M["acoustic"])
    # violet LED strip: a slim aluminium channel just above the desk, grazing the panels from below
    box("led_channel", -1.7, 1.0, D1 - 0.06, D1 - 0.02, 0.93, 0.95, M["steel"])
    box("violet_strip", -1.68, 0.98, D1 - 0.055, D1 - 0.025, 0.95, 0.955, M["violet_led"], collection="EMISSIVE")

    # --- MIDI controller (37 keys + pads)
    kx0, kx1, ky0, ky1 = -1.48, -0.72, 5.5, 5.8
    box("midi_body", kx0, kx1, ky0 + 0.14, ky1, top_z, top_z + 0.045, M["plastic_black"], bevel=0.008)
    box("midi_keybed", kx0, kx1, ky0, ky0 + 0.145, top_z, top_z + 0.02, M["plastic_black"], bevel=0.004)
    box("midi_cheek_l", kx0, kx0 + 0.018, ky0, ky0 + 0.145, top_z, top_z + 0.045, M["plastic_black"], bevel=0.004)
    box("midi_cheek_r", kx1 - 0.018, kx1, ky0, ky0 + 0.145, top_z, top_z + 0.045, M["plastic_black"], bevel=0.004)
    top = plane("midi_top", [(kx0 + 0.01, ky0 + 0.145, top_z + 0.0455), (kx1 - 0.01, ky0 + 0.145, top_z + 0.0455),
                             (kx1 - 0.01, ky1 - 0.01, top_z + 0.0455), (kx0 + 0.01, ky1 - 0.01, top_z + 0.0455)],
                M["midi_top"], uv=[(0, 0), (1, 0), (1, 1), (0, 1)])
    top["decal"] = 1
    nwhite = 22
    kw = (kx1 - kx0 - 0.04) / nwhite
    for i in range(nwhite):
        x = kx0 + 0.02 + i * kw
        box(f"key_w_{i}", x + 0.0007, x + kw - 0.0007, ky0 + 0.005, ky0 + 0.135, top_z + 0.02, top_z + 0.038,
            M["key_white"], bevel=0.0015, segs=1)
        if i % 7 not in (2, 6) and i < nwhite - 1:
            box(f"key_b_{i}", x + kw * 0.68, x + kw * 1.32, ky0 + 0.055, ky0 + 0.135, top_z + 0.038, top_z + 0.05,
                M["key_black"], bevel=0.0015, segs=1)

    # --- laptop (base static, lid + screen dynamic)
    lx, ly = -0.27, 5.72
    lw, ld = 0.31, 0.215
    box("laptop_base", lx - lw / 2, lx + lw / 2, ly - ld / 2, ly + ld / 2, top_z, top_z + 0.014, M["laptop"], bevel=0.004)
    box("laptop_keys", lx - 0.13, lx + 0.13, ly - 0.01, ly + 0.09, top_z + 0.0141, top_z + 0.0145, M["laptop_key"])
    box("laptop_pad", lx - 0.055, lx + 0.055, ly - 0.095, ly - 0.03, top_z + 0.0141, top_z + 0.0143, M["laptop"])
    # lid hinged at back edge, opened ~105deg
    hinge = Vector((lx, ly + ld / 2, top_z + 0.012))
    lid = box("laptop_lid", -lw / 2, lw / 2, -0.006, 0.0, 0, 0.205, M["laptop"], bevel=0.003, collection="STATIC")
    lid_rot = Matrix.Translation(hinge) @ Matrix.Rotation(math.radians(-14), 4, "X")
    lid.data.transform(lid_rot)
    scr = plane("Laptop_Screen", [(-0.142, -0.0065, 0.012), (0.142, -0.0065, 0.012), (0.142, -0.0065, 0.193),
                                  (-0.142, -0.0065, 0.193)], M["screen"], collection="EMISSIVE",
                uv=[(0, 0), (1, 0), (1, 1), (0, 1)])
    scr.data.transform(lid_rot)
    scr["decal"] = 1

    # --- desk lamp: base back-right, arm reaching over laptop and keys, shade aimed down
    base = Vector((0.28, 5.98, top_z))
    cyl("lamp_base", (base.x, base.y, top_z + 0.012), 0.075, 0.024, M["lampshade"], segs=28, bevel=0.004)
    elbow = Vector((0.12, 5.92, top_z + 0.55))
    head = Vector((-0.5, 5.66, top_z + 0.46))
    for nm, a, b in (("lamp_arm1", base + Vector((0, 0, 0.02)), elbow), ("lamp_arm2", elbow, head + Vector((0.06, 0.02, 0.03)))):
        d = b - a
        ob = cyl(nm, (0, 0, 0), 0.008, d.length, M["steel"], segs=10)
        ob.data.transform(Matrix.Translation((a + b) / 2) @ d.to_track_quat("Z", "Y").to_matrix().to_4x4())
    sphere("lamp_joint", elbow, 0.018, M["lampshade"], segs=12, rings=8)
    # shade: open cone pointing down & slightly back toward the wall
    shade = cyl("lamp_shade", (0, 0, 0), 0.03, 0.13, M["lampshade"], r2=0.085, segs=32, cap=False)
    lamp_target = Vector((-0.66, 5.74, top_z))   # between the keys and the laptop
    aim_dir = (lamp_target - head).normalized()
    sm = Matrix.Translation(head) @ aim_dir.to_track_quat("Z", "Y").to_matrix().to_4x4()
    shade.data.transform(sm)
    sol = shade.modifiers.new("sol", "SOLIDIFY")
    sol.thickness = 0.003
    apply_mods(shade)
    bulb_pos = sm @ Vector((0, 0, -0.025))
    sphere("Lamp_Bulb", bulb_pos, 0.024, M["bulb"], collection="EMISSIVE")
    # lamp light (spot) lives with the shade orientation
    lamp_dir = aim_dir

    # --- props on desk
    cyl("mug", (0.48, 5.6, top_z + 0.05), 0.04, 0.1, M["mug"], segs=24, bevel=0.003)
    tube("mug_handle", [(0.52, 5.6, top_z + 0.08), (0.56, 5.6, top_z + 0.05), (0.52, 5.6, top_z + 0.02)], 0.007, M["mug"])
    box("notebook", 0.22, 0.42, 5.5, 5.64, top_z, top_z + 0.012, M["paper"], bevel=0.002)
    box("pencil", 0.25, 0.4, 5.52, 5.528, top_z + 0.012, top_z + 0.019, M["desk_edge"])
    tape = plane("tape_desk", [(-1.0, 5.452, top_z - 0.032), (-0.62, 5.452, top_z - 0.032),
                               (-0.62, 5.452, top_z - 0.006), (-1.0, 5.452, top_z - 0.006)], M["tape_labels"],
                 uv=[(0, 0.75), (0.5, 0.75), (0.5, 1), (0, 1)])
    tape["decal"] = 1
    # audio interface
    box("interface", 0.1, 0.32, 5.62, 5.76, top_z, top_z + 0.045, M["rack"], bevel=0.006)
    for i in range(2):
        cyl(f"interface_knob_{i}", (0.15 + i * 0.07, 5.618, top_z + 0.024), 0.011, 0.012, M["plastic_black"], axis="Y", segs=16)
    sphere("interface_led", (0.29, 5.618, top_z + 0.034), 0.0025, M["led_amber"], collection="EMISSIVE")
    # headphones resting on the desk corner
    tube("headphones", [(0.62, 5.95, top_z + 0.01), (0.66, 5.9, top_z + 0.11), (0.74, 5.88, top_z + 0.12),
                        (0.78, 5.92, top_z + 0.01)], 0.012, M["plastic_black"])
    for x in (0.62, 0.78):
        cyl(f"earcup_{x}", (x, 5.93, top_z + 0.03), 0.04, 0.03, M["rubber"], axis="X", segs=20, bevel=0.006)
    return lamp_dir, bulb_pos, Vector((lx, ly + ld / 2 - 0.02, top_z + 0.11))


def build_rack_and_case(M):
    # gear rack, left of desk
    x0, x1, y0, y1 = -2.42, -1.86, 5.72, 6.16
    box("rack_frame", x0, x1, y0, y1, 0.06, 1.08, M["rack"], bevel=0.008)
    face = plane("rack_face", [(x0 + 0.03, y0 - 0.002, 0.12), (x1 - 0.03, y0 - 0.002, 0.12),
                               (x1 - 0.03, y0 - 0.002, 1.02), (x0 + 0.03, y0 - 0.002, 1.02)],
                 M["rack_faces"], uv=[(0, 0), (1, 0), (1, 1), (0, 1)])
    face["decal"] = 1
    for x in (x0 + 0.05, x1 - 0.05):
        for y in (y0 + 0.05, y1 - 0.05):
            cyl(f"caster_{x:.2f}_{y:.2f}", (x, y, 0.03), 0.028, 0.03, M["rubber"], axis="X", segs=12)
    # purplhrtz tape strip on top lip of the rack
    t = plane("tape_purplhrtz", [(x0 + 0.06, y0 - 0.0035, 1.032), (x1 - 0.04, y0 - 0.0035, 1.03),
                                 (x1 - 0.04, y0 - 0.0035, 1.068), (x0 + 0.06, y0 - 0.0035, 1.07)],
              M["tape_purplhrtz"], uv=[(0, 0), (1, 0), (1, 1), (0, 1)])
    t["decal"] = 1
    for i in range(5):
        sphere(f"rack_led_{i}", (x1 - 0.06, y0 - 0.003, 0.2 + i * 0.17), 0.004,
               M["led_violet"] if i % 2 else M["led_amber"], collection="EMISSIVE")
    # small synth on top of rack
    box("synth", x0 + 0.02, x1 - 0.02, y0 + 0.05, y1 - 0.02, 1.08, 1.14, M["plastic_grey"], bevel=0.01)
    for i in range(5):
        cyl(f"synth_knob_{i}", (x0 + 0.08 + i * 0.09, y0 + 0.12, 1.15), 0.012, 0.02, M["plastic_black"], segs=14)
    # cables from rack to desk
    tube("cable_a", [(x1 - 0.02, y1 - 0.1, 0.3), (-1.7, 6.05, 0.02), (-1.2, 6.1, 0.02), (-0.4, 6.08, 0.15),
                     (-0.27, 6.08, 0.74)], 0.006, M["cable"])
    tube("cable_b", [(x1 - 0.02, y1 - 0.15, 0.5), (-1.75, 5.95, 0.01), (0.2, 6.02, 0.01), (0.9, 6.1, 0.02),
                     (1.01, 6.17, 0.38)], 0.005, M["cable"])
    tube("cable_lamp", [(0.28, 6.05, 0.77), (0.4, 6.15, 0.6), (0.5, 6.16, 0.02), (1.0, 6.15, 0.02),
                        (1.01, 6.17, 0.34)], 0.0045, M["cable"])

    # road case (Barry's spot), right of the desk, blanket on top
    cx0, cx1, cy0, cy1, ch = 1.0, 1.62, 5.28, 5.9, 0.5
    box("roadcase", cx0, cx1, cy0, cy1, 0.0, ch, M["roadcase"], bevel=0.012)
    for (a, b) in ((cx0, cy0), (cx1, cy0), (cx0, cy1), (cx1, cy1)):
        box(f"case_corner_{a}_{b}", a - 0.012, a + 0.012, b - 0.012, b + 0.012, ch - 0.06, ch + 0.005, M["steel"], bevel=0.004)
    box("case_edge", cx0 - 0.006, cx1 + 0.006, cy0 - 0.006, cy0 + 0.006, ch - 0.1, ch - 0.08, M["steel"])
    box("case_handle", 1.2, 1.42, cy0 - 0.03, cy0 - 0.012, 0.28, 0.31, M["steel"], bevel=0.004)
    lbl = plane("case_label", [(cx0 + 0.06, cy0 - 0.0065, 0.36), (cx0 + 0.3, cy0 - 0.0065, 0.36),
                               (cx0 + 0.3, cy0 - 0.0065, 0.42), (cx0 + 0.06, cy0 - 0.0065, 0.42)],
                M["tape_labels"], uv=[(0.5, 0.5), (1, 0.5), (1, 0.75), (0.5, 0.75)])
    lbl["decal"] = 1
    # blanket: a draped, folded slab — subdivided grid displaced over the case top & down the front
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=28, y_segments=28, size=0.5)
    r = random.Random(3)
    for v in bm.verts:
        u, w = v.co.x, v.co.y  # -0.5..0.5
        x = 1.31 + u * 0.82
        y = 5.6 + w * 0.82
        z = ch + 0.035
        # drape down front edge (cy0) and right side
        if y < cy0 + 0.02:
            z = ch + 0.03 - (cy0 + 0.02 - y) * 1.6
            y = cy0 - 0.02 - (cy0 + 0.02 - y) * 0.12
        if x > cx1 - 0.02:
            z = min(z, ch + 0.03 - (x - cx1 + 0.02) * 1.5)
            x = cx1 + 0.02 + (x - cx1 + 0.02) * 0.1
        if x < cx0 + 0.04:
            z = min(z, ch + 0.03 - (cx0 + 0.04 - x) * 1.5)
            x = cx0 - 0.015 - (cx0 + 0.04 - x) * 0.1
        # folds and the nest Barry made
        z += 0.012 * math.sin(u * 19 + 1.3) * math.sin(w * 11) + r.uniform(-0.003, 0.003)
        nest = math.exp(-(((x - 1.31) / 0.2) ** 2 + ((y - 5.6) / 0.18) ** 2))
        z -= 0.018 * nest
        z += 0.03 * math.exp(-(((x - 1.31) / 0.26) ** 2 + ((y - 5.6) / 0.24) ** 2)) * (1 - nest) * 1.2
        v.co = Vector((x, y, max(z, 0.02)))
    sol = new_obj("blanket", bm, M["blanket"])
    m = sol.modifiers.new("s", "SOLIDIFY")
    m.thickness = 0.012
    apply_mods(sol)
    smooth(sol, 80)


def build_couch_and_wall(M):
    # couch along right wall
    x0, x1, y0, y1 = W0 + 0.02, W0 + 0.88, 1.75, 3.75
    box("couch_base", x0, x1, y0, y1, 0.08, 0.36, M["couch"], bevel=0.04, segs=3)
    box("couch_back", x0, x0 + 0.2, y0, y1, 0.36, 0.82, M["couch"], bevel=0.06, segs=3)
    for i, (a, b) in enumerate(((y0, y0 + 0.2), (y1 - 0.2, y1))):
        box(f"couch_arm_{i}", x0, x1, a, b, 0.36, 0.62, M["couch"], bevel=0.07, segs=3)
    for i in range(2):
        a = y0 + 0.2 + i * 0.825
        cush = box(f"couch_cushion_{i}", x0 + 0.2, x1 - 0.02, a + 0.01, a + 0.815, 0.36, 0.48, M["couch"], bevel=0.05, segs=3)
    for x, y in ((x0 + 0.06, y0 + 0.06), (x0 + 0.06, y1 - 0.06), (x1 - 0.06, y0 + 0.06), (x1 - 0.06, y1 - 0.06)):
        cyl(f"couch_foot_{x}_{y}", (x, y, 0.04), 0.022, 0.08, M["desk_edge"], segs=10)
    # throw pillow
    p = sphere("pillow", (W0 + 0.33, 3.35, 0.6), 0.2, M["acoustic_plum"], scale=(0.45, 1.0, 0.9), segs=20, rings=12)
    # floor lamp is off; side table w/ vinyl sleeve
    box("side_table", W0 + 0.05, W0 + 0.5, 3.85, 4.25, 0.0, 0.48, M["desk"], bevel=0.01)

    # corkboard on the left wall near the back corner
    cb = (W0 + 0.0, 4.3, 5.45, 0.98, 1.82)
    box("cork_frame", W0, W0 + 0.035, cb[1] - 0.03, cb[2] + 0.03, cb[3] - 0.03, cb[4] + 0.03, M["desk_edge"], bevel=0.005)
    box("corkboard", W0 + 0.002, W0 + 0.04, cb[1], cb[2], cb[3], cb[4], M["cork"])
    # pinned paper notes + flyers on the corkboard (static decoration; live notes render in HTML)
    r = random.Random(11)
    notes = [(4.42, 1.5, 0.16, 0.2, "paper"), (4.68, 1.6, 0.14, 0.14, "paper_violet"), (4.95, 1.45, 0.17, 0.12, "paper"),
             (4.5, 1.15, 0.15, 0.15, "paper"), (5.2, 1.2, 0.14, 0.17, "paper_violet")]
    for i, (y, z, w, h, mat) in enumerate(notes):
        x = W0 + 0.042 + i * 0.0006
        ob = plane(f"cork_note_{i}", [(x, y, z), (x, y + w, z + r.uniform(-0.01, 0.01)), (x, y + w, z + h),
                                       (x, y, z + h)], M[mat])
        sphere(f"cork_pin_{i}", (x + 0.006, y + w / 2, z + h - 0.015), 0.007, M["pin"], segs=10, rings=6)
    fl = plane("cork_flyer", [(W0 + 0.045, 5.05, 1.38), (W0 + 0.045, 5.38, 1.38), (W0 + 0.045, 5.38, 1.8),
                              (W0 + 0.045, 5.05, 1.8)], M["flyer_b"], uv=[(0, 0), (1, 0), (1, 1), (0, 1)], subdiv=6)
    fl["decal"] = 1
    bend(fl, Vector((W0 + 0.045, 5.38, 1.38)), math.radians(-25), deform_axis="Y")

    # curling gig flyers taped to the block walls
    for nm, mat, corners, ang in (
        ("flyer_wall_a", "flyer_a", [(1.18, D1 - 0.003, 1.3), (1.5, D1 - 0.003, 1.3), (1.5, D1 - 0.003, 1.75), (1.18, D1 - 0.003, 1.75)], 30),
        ("flyer_wall_c", "flyer_c", [(W1 - 0.003, 4.4, 1.35), (W1 - 0.003, 4.1, 1.35), (W1 - 0.003, 4.1, 1.77), (W1 - 0.003, 4.4, 1.77)], -22),
    ):
        f = plane(nm, corners, M[mat], uv=[(0, 0), (1, 0), (1, 1), (0, 1)], subdiv=8)
        f["decal"] = 1
        bot = Vector(corners[0])
        # lift the bottom corner off the wall: curl around a horizontal axis at the top
        for v in f.data.vertices:
            t = (corners[2][2] - v.co.z) / (corners[2][2] - corners[0][2])
            lift = 0.06 * t ** 2.4 * (1 if mat != "flyer_c" else 1.2)
            if abs(corners[0][1] - corners[1][1]) < 1e-6:
                v.co.x -= lift
            else:
                v.co.y -= lift * (1 if corners[0][1] > 4 else -1) * 0
                v.co.y += 0
                v.co.x -= lift
        if abs(corners[0][1] - corners[1][1]) < 1e-6:
            # back wall flyer: curl along -Y
            for v in f.data.vertices:
                t = (corners[2][2] - v.co.z) / (corners[2][2] - corners[0][2])
                v.co.y -= 0.06 * t ** 2.4
                v.co.x += 0
        # tape bits
    for i, (x, y, z, axis) in enumerate(((1.34, D1 - 0.004, 1.76, "Y"), (W1 - 0.004, 4.25, 1.78, "X"))):
        if axis == "Y":
            plane(f"flyer_tape_{i}", [(x - 0.04, y - 0.001, z - 0.02), (x + 0.04, y - 0.001, z - 0.02),
                                      (x + 0.04, y - 0.001, z + 0.015), (x - 0.04, y - 0.001, z + 0.015)], M["paper"])
        else:
            plane(f"flyer_tape_{i}", [(x - 0.001, y - 0.04, z - 0.02), (x - 0.001, y + 0.04, z - 0.02),
                                      (x - 0.001, y + 0.04, z + 0.015), (x - 0.001, y - 0.04, z + 0.015)], M["paper"])
    # guitar on a stand by the couch (simple silhouette)
    gx, gy = 2.3, 3.2   # guitar on a stand against the right wall
    body = sphere("guitar_body", (gx, gy, 0.34), 0.17, M["desk"], scale=(0.4, 1.0, 1.25), segs=24, rings=12)
    box("guitar_neck", gx + 0.02, gx + 0.05, gy - 0.03, gy + 0.03, 0.5, 1.12, M["desk_edge"])
    box("guitar_head", gx + 0.02, gx + 0.06, gy - 0.04, gy + 0.04, 1.12, 1.24, M["plastic_black"], bevel=0.005)
    tube("guitar_stand", [(gx, gy - 0.2, 0.0), (gx + 0.05, gy, 0.2), (gx, gy + 0.2, 0.0)], 0.008, M["rack"])
    # stair-top glow (upstairs light spilling down) — emissive panel far up the stairwell
    plane("stair_glow", [(JAMB_X + 0.05, F - 2.6, 2.3), (W1 - 0.05, F - 2.6, 2.3), (W1 - 0.05, F - 2.6, 3.2), (JAMB_X + 0.05, F - 2.6, 3.2)],
          M["stair_glow"], collection="EMISSIVE")


# ================================================================ Barry
def fur_material():
    m = bpy.data.materials.get("barry_fur")
    if m:
        return m
    m = bpy.data.materials.new("barry_fur")
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    bsdf.inputs["Roughness"].default_value = 0.85
    bsdf.inputs["Sheen Weight"].default_value = 0.8
    bsdf.inputs["Sheen Roughness"].default_value = 0.4
    bsdf.inputs["Sheen Tint"].default_value = (1.0, 0.75, 0.5, 1)
    bsdf.inputs["Subsurface Weight"].default_value = 0.08
    bsdf.inputs["Subsurface Radius"].default_value = (0.9, 0.4, 0.2)
    bsdf.inputs["Subsurface Scale"].default_value = 0.01
    # tabby: radial stripes around the curl centre, darker saddle on top, cream underside
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Object"], sep.inputs[0])
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 9.0
    noise.inputs["Detail"].default_value = 6.0
    nt.links.new(tc.outputs["Object"], noise.inputs["Vector"])
    at = nt.nodes.new("ShaderNodeMath"); at.operation = "ARCTAN2"
    nt.links.new(sep.outputs["Y"], at.inputs[0]); nt.links.new(sep.outputs["X"], at.inputs[1])
    mul = nt.nodes.new("ShaderNodeMath"); mul.operation = "MULTIPLY"; mul.inputs[1].default_value = 19.0
    nt.links.new(at.outputs[0], mul.inputs[0])
    nmul = nt.nodes.new("ShaderNodeMath"); nmul.operation = "MULTIPLY"; nmul.inputs[1].default_value = 4.5
    nt.links.new(noise.outputs["Fac"], nmul.inputs[0])
    add = nt.nodes.new("ShaderNodeMath"); add.operation = "ADD"
    nt.links.new(mul.outputs[0], add.inputs[0]); nt.links.new(nmul.outputs[0], add.inputs[1])
    sn = nt.nodes.new("ShaderNodeMath"); sn.operation = "SINE"
    nt.links.new(add.outputs[0], sn.inputs[0])
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.25
    ramp.color_ramp.elements[0].color = (0.24, 0.075, 0.02, 1)
    ramp.color_ramp.elements[1].position = 0.8
    ramp.color_ramp.elements[1].color = (0.72, 0.31, 0.085, 1)
    mapr = nt.nodes.new("ShaderNodeMapRange")
    mapr.inputs["From Min"].default_value = -1; mapr.inputs["From Max"].default_value = 1
    nt.links.new(sn.outputs[0], mapr.inputs["Value"])
    # fade stripes toward the crown of the curl and break them up so they never read as a pumpkin
    vl = nt.nodes.new("ShaderNodeVectorMath"); vl.operation = "LENGTH"
    cxy = nt.nodes.new("ShaderNodeCombineXYZ")
    nt.links.new(sep.outputs["X"], cxy.inputs["X"]); nt.links.new(sep.outputs["Y"], cxy.inputs["Y"])
    nt.links.new(cxy.outputs[0], vl.inputs[0])
    fade = nt.nodes.new("ShaderNodeMapRange")
    fade.inputs["From Min"].default_value = 0.025; fade.inputs["From Max"].default_value = 0.075
    nt.links.new(vl.outputs["Value"], fade.inputs["Value"])
    brk = nt.nodes.new("ShaderNodeTexNoise"); brk.inputs["Scale"].default_value = 22; brk.inputs["Detail"].default_value = 3
    nt.links.new(tc.outputs["Object"], brk.inputs["Vector"])
    brkr = nt.nodes.new("ShaderNodeMapRange")
    brkr.inputs["From Min"].default_value = 0.3; brkr.inputs["From Max"].default_value = 0.48
    nt.links.new(brk.outputs["Fac"], brkr.inputs["Value"])
    amt = nt.nodes.new("ShaderNodeMath"); amt.operation = "MULTIPLY"
    nt.links.new(fade.outputs[0], amt.inputs[0]); nt.links.new(brkr.outputs[0], amt.inputs[1])
    mixf = nt.nodes.new("ShaderNodeMix"); mixf.data_type = "FLOAT"
    mixf.inputs["A"].default_value = 0.62
    nt.links.new(amt.outputs[0], mixf.inputs["Factor"])
    nt.links.new(mapr.outputs[0], mixf.inputs["B"])
    nt.links.new(mixf.outputs["Result"], ramp.inputs["Fac"])
    # cream underside by Z (object space)
    zr = nt.nodes.new("ShaderNodeMapRange"); zr.name = "cream_z"
    zr.inputs["From Min"].default_value = 0.028; zr.inputs["From Max"].default_value = 0.006
    nt.links.new(sep.outputs["Z"], zr.inputs["Value"])
    cream = nt.nodes.new("ShaderNodeMix"); cream.data_type = "RGBA"
    cream.inputs["B"].default_value = (0.8, 0.55, 0.32, 1)
    nt.links.new(zr.outputs[0], cream.inputs["Factor"])
    nt.links.new(ramp.outputs["Color"], cream.inputs["A"])
    # fine fur value noise
    fn = nt.nodes.new("ShaderNodeTexNoise"); fn.inputs["Scale"].default_value = 160; fn.inputs["Detail"].default_value = 2
    nt.links.new(tc.outputs["Object"], fn.inputs["Vector"])
    fmix = nt.nodes.new("ShaderNodeMix"); fmix.data_type = "RGBA"; fmix.blend_type = "MULTIPLY"
    fmix.inputs["Factor"].default_value = 0.35
    nt.links.new(cream.outputs["Result"], fmix.inputs["A"])
    nt.links.new(fn.outputs["Color"], fmix.inputs["B"])
    nt.links.new(fmix.outputs["Result"], bsdf.inputs["Base Color"])
    m["procedural"] = 1
    return m


def metaball_mesh(name, elements, resolution=0.006, collection="BARRY"):
    mb = bpy.data.metaballs.new(name + "_mb")
    mb.resolution = resolution
    mb.render_resolution = resolution
    mb.threshold = 0.6
    for (co, rad, scale) in elements:
        e = mb.elements.new()
        e.type = "ELLIPSOID"
        e.co = co
        e.radius = rad
        e.size_x, e.size_y, e.size_z = scale
        e.stiffness = 2.0
    ob = bpy.data.objects.new(name, mb)
    coll(collection).objects.link(ob)
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    mesh_ob = bpy.data.objects.new(name, me)
    coll(collection).objects.link(mesh_ob)
    bpy.data.objects.remove(ob)
    bpy.data.metaballs.remove(mb)
    mesh_ob.name = name
    return mesh_ob


def decimate(ob, ratio):
    m = ob.modifiers.new("dec", "DECIMATE")
    m.ratio = ratio
    apply_mods(ob)


def build_barry(M):
    """Provisional procedural orange tabby, curled asleep. Parts are separate for runtime animation.
    Local frame: origin on the blanket under the body centre; +X toward his head side."""
    fur = fur_material()
    els = []
    # body: a compact curled mound — spine arc (r=0.07) from hips (170deg) round to shoulders (-20deg)
    for i in range(12):
        t = i / 11
        a = math.radians(170 - 190 * t)
        r = 0.068
        size = 0.094 - 0.016 * t + 0.008 * math.sin(t * math.pi)
        els.append(((r * math.cos(a), r * math.sin(a), 0.062 - 0.008 * t), 1.0,
                    (size, size * 0.92, size * 0.78)))
    els.append(((-0.045, 0.045, 0.078), 1.0, (0.09, 0.085, 0.075)))     # haunch
    els.append(((0.0, 0.0, 0.05), 1.0, (0.08, 0.08, 0.06)))             # fill the centre: no donut
    els.append(((0.085, 0.085, 0.022), 1.0, (0.04, 0.026, 0.02)))       # hind paw
    els.append(((0.13, -0.085, 0.02), 1.0, (0.05, 0.024, 0.018)))      # front paws under the chin
    els.append(((0.15, -0.04, 0.018), 1.0, (0.045, 0.022, 0.016)))
    body = metaball_mesh("Barry_Body", els)
    # head (separate, pivot at the neck) — chin resting on the paws
    head_els = [((0, 0, 0), 1.0, (0.06, 0.058, 0.05)),
                ((0.036, 0.0, -0.014), 1.0, (0.032, 0.034, 0.024)),        # muzzle
                ((0.006, 0.032, -0.008), 1.0, (0.036, 0.03, 0.032)),       # cheeks
                ((0.006, -0.032, -0.008), 1.0, (0.036, 0.03, 0.032))]
    head = metaball_mesh("Barry_Head", head_els, resolution=0.004)
    tail_pts = [(-0.15, 0.07, 0.035), (-0.19, -0.05, 0.026), (-0.11, -0.165, 0.022), (0.02, -0.195, 0.02), (0.13, -0.165, 0.022)]
    tail = tube("Barry_Tail", tail_pts, 0.022, None, collection="BARRY", res=10)
    # taper toward the tip
    pts = [Vector(p) for p in tail_pts]
    for v in tail.data.vertices:
        nearest = min(range(len(pts)), key=lambda k: (pts[k] - v.co).length)
        t = nearest / (len(pts) - 1)
        c = pts[nearest]
        v.co = c + (v.co - c) * (1.0 - 0.45 * t)
    fur_head = fur.copy(); fur_head.name = "barry_fur_head"
    zr = fur_head.node_tree.nodes["cream_z"]
    zr.inputs["From Min"].default_value = -0.008
    zr.inputs["From Max"].default_value = -0.03
    for ob, m in ((body, fur), (head, fur_head), (tail, fur)):
        ob.data.materials.clear()
        ob.data.materials.append(m)
        smooth(ob, 180)
    decimate(body, 0.35); decimate(head, 0.4)
    # ears (children of head)
    ear_mat_in = material("barry_ear_in", color=(0.35, 0.12, 0.1), rough=0.8, sheen=0.4)
    ears = []
    for side, s in (("L", 1), ("R", -1)):
        bm = bmesh.new()
        bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=True, segments=12, radius1=0.021, radius2=0.005, depth=0.032)
        bmesh.ops.scale(bm, vec=(1.0, 0.55, 1.0), verts=bm.verts)
        bmesh.ops.translate(bm, vec=(0, 0, 0.017), verts=bm.verts)
        e = new_obj(f"Barry_Ear{side}", bm, material("barry_ear", color=(0.42, 0.16, 0.045), rough=0.8, sheen=0.6), collection="BARRY")
        e.data.materials.append(ear_mat_in)
        for p in e.data.polygons:
            if p.center.y < -0.004 and p.center.z > 0.004:
                p.material_index = 1
        smooth(e, 60)
        ears.append((e, s))
    # eyes (children of head) — almond, amber-green, scaled flat when closed
    eye_mat = material("barry_eye", color=(0.55, 0.5, 0.1), rough=0.05, coat=1.0)
    eyes = []
    for side, s in (("L", 1), ("R", -1)):
        e = sphere(f"Barry_Eye{side}", (0, 0, 0), 0.011, eye_mat, scale=(0.6, 1.0, 0.75), segs=16, rings=8, collection="BARRY")
        eyes.append((e, s))
    nose_mat = material("barry_nose", color=(0.45, 0.2, 0.18), rough=0.4)
    nose = sphere("Barry_Nose", (0, 0, 0), 0.006, nose_mat, scale=(0.7, 1.2, 0.7), segs=10, rings=6, collection="BARRY")
    whisker_mat = material("barry_whisker", color=(0.85, 0.82, 0.75), rough=0.4)

    # place hierarchy
    root = bpy.data.objects.new("Barry", None)
    coll("BARRY").objects.link(root)
    root.location = (1.31, 5.6, 0.5 + 0.035 - 0.012)
    root.rotation_euler = (0, 0, math.radians(-128))   # head toward camera-left / laptop light
    for ob in (body, tail):
        ob.parent = root
    neck = Vector((0.12, -0.075, 0.062))
    head.parent = root
    head.location = neck
    head.rotation_euler = (math.radians(8), math.radians(14), math.radians(-35))
    for e, s in ears:
        e.parent = head
        e.location = (-0.008, 0.03 * s, 0.038)
        e.rotation_euler = (math.radians(-22 * s), math.radians(-10), math.radians(15 * s))
    for e, s in eyes:
        e.parent = head
        e.location = (0.045, 0.021 * s, 0.01)
        e.rotation_euler = (0, math.radians(-8), math.radians(18 * s))
        e.scale = (1, 1, 0.12)   # asleep
    nose.parent = head
    nose.location = (0.066, 0, -0.008)
    for s in (1, -1):
        for k in range(3):
            w = tube(f"Barry_Whisker_{s}_{k}", [(0.058, 0.018 * s, -0.012 - k * 0.004),
                                               (0.085, 0.05 * s, -0.012 - k * 0.006),
                                               (0.1, 0.085 * s, -0.02 - k * 0.01)], 0.0006, whisker_mat, collection="BARRY", res=4)
            w.parent = head
    return root


# ================================================================ lights + world
def aim(ob, direction):
    """Blender lights emit along local -Z."""
    ob.rotation_euler = Vector(direction).normalized().to_track_quat("-Z", "Y").to_euler()


def build_lights(lamp_dir, bulb_pos, screen_pos):
    L = {}

    def light(name, kind, loc, energy, color, group, **kw):
        ld = bpy.data.lights.new(name, kind)
        ld.energy = energy
        ld.color = color
        for k, v in kw.items():
            setattr(ld, k, v)
        ob = bpy.data.objects.new(name, ld)
        ob.location = loc
        coll("LIGHTS").objects.link(ob)
        ob["group"] = group
        L[name] = ob
        return ob

    sp = light("lamp_spot", "SPOT", bulb_pos, 110.0, LAMP_RGB, "lamp", spot_size=math.radians(92),
               spot_blend=0.75, shadow_soft_size=0.025)
    aim(sp, lamp_dir)
    # cheat: a soft, narrow spill from the lamp toward Barry's blanket (switches with the lamp)
    bf = light("lamp_barry_fill", "SPOT", bulb_pos, 13.0, LAMP_RGB, "lamp", spot_size=math.radians(18),
               spot_blend=1.0, shadow_soft_size=0.12)
    aim(bf, Vector((1.31, 5.55, 0.6)) - bulb_pos)
    # leak through the top of the shade (very soft) — keeps the ceiling from going pure black
    light("lamp_leak", "POINT", bulb_pos + Vector((0, 0, 0.06)), 4.0, LAMP_RGB, "lamp", shadow_soft_size=0.05)
    # violet strip: thin area light pointing up the wall
    v = light("violet_area", "AREA", (-0.35, D1 - 0.04, 0.96), 16.0, VIOLET_RGB, "violet", shape="RECTANGLE",
              size=2.6, size_y=0.02)
    aim(v, (0, 0.28, 1))  # grazes up the panels
    # laptop screen
    s = light("screen_area", "AREA", screen_pos + Vector((0, -0.012, 0)), 2.2, SCREEN_RGB, "screen",
              shape="RECTANGLE", size=0.28, size_y=0.18)
    aim(s, (0, -0.97, -0.24))
    # ambient: stairwell spill from upstairs + a whisper of fill
    a = light("stair_area", "AREA", (2.05, F - 1.3, 2.7), 110.0, STAIR_RGB, "ambient", shape="RECTANGLE",
              size=1.0, size_y=0.8)
    aim(a, (-0.15, 0.55, -1.0))
    light("monitor_glow", "POINT", (-0.4, 4.6, 1.9), 3.0, (0.55, 0.45, 0.8), "ambient", shadow_soft_size=1.0)
    return L


def setup_world():
    w = bpy.data.worlds.new("world")
    bpy.context.scene.world = w
    w.use_nodes = True if hasattr(w, "use_nodes") else None
    bg = w.node_tree.nodes.get("Background")
    bg.inputs["Color"].default_value = (0.004, 0.0035, 0.005, 1)
    bg.inputs["Strength"].default_value = 1.0


DEBUG_SHOTS = {
    "dbg_barry": ((0.75, 4.75, 0.95), (1.31, 5.6, 0.56), 30.0),
    "dbg_desk": ((-0.3, 4.55, 1.2), (-0.4, 5.75, 0.85), 40.0),
    "dbg_cork": ((-1.2, 4.85, 1.45), (-2.6, 4.88, 1.4), 45.0),
    "dbg_back": ((-0.5, 4.2, 1.4), (1.8, 0.8, 1.1), 60.0),
    "dbg_barry_close": ((1.0, 5.05, 0.78), (1.33, 5.58, 0.56), 26.0),
    "dbg_couch": ((-1.9, 2.6, 1.05), (0.2, 5.5, 0.8), 50.0),
}


def setup_cameras():
    for key, (pos, tgt, fov) in {**SHOTS, **DEBUG_SHOTS}.items():
        cd = bpy.data.cameras.new(key)
        cd.sensor_fit = "VERTICAL"
        cd.angle_y = math.radians(fov)
        cd.clip_start = 0.05
        cd.clip_end = 40
        cd.dof.use_dof = True
        cd.dof.aperture_fstop = 2.8
        ob = bpy.data.objects.new("CAM_" + key, cd)
        coll("CAMS").objects.link(ob)
        ob.location = pos
        d = Vector(tgt) - Vector(pos)
        ob.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
        cd.dof.focus_distance = (Vector(tgt) - Vector(pos)).length if key.startswith("dbg") else \
            (Vector((-0.27, 5.7, 0.86)) - Vector(pos)).length


# ================================================================ build stage
def stage_build():
    clear_scene()
    M = build_materials()
    build_room(M)
    lamp_dir, bulb_pos, screen_pos = build_desk(M)
    build_rack_and_case(M)
    build_couch_and_wall(M)
    build_barry(M)
    build_lights(lamp_dir, bulb_pos, screen_pos)
    setup_world()
    setup_cameras()
    # UVs: box-mapped textures for everything static except decals
    for ob in coll("STATIC").objects:
        if ob.type != "MESH":
            continue
        if ob.get("decal"):
            if not ob.data.uv_layers:
                decal_uv(ob)
            continue
        box_uv(ob)
        smooth(ob, 35)
    for ob in coll("EMISSIVE").objects:
        ob.visible_shadow = False  # practicals: lights live inside/near them
        if ob.type == "MESH" and not ob.data.uv_layers:
            decal_uv(ob)
    bpy.ops.wm.save_as_mainfile(filepath=BLEND)
    print("built", len(coll("STATIC").objects), "static objects")


# ================================================================ bake stage
def prune_hidden_faces(ob):
    """Remove faces nobody can see (outside the shell, under the floor, on top of walls) so they
    don't waste lightmap texels."""
    me = ob.data
    bm = bmesh.new()
    bm.from_mesh(me)
    mw = ob.matrix_world
    kill = []
    for f in bm.faces:
        c = mw @ f.calc_center_median()
        n = (mw.to_3x3() @ f.normal).normalized()
        outside = c.x < W0 - 0.01 or c.x > W1 + 0.01 or c.y > D1 + 0.01 or c.z < -0.01 or c.z > H + 0.01
        if outside or (n.z < -0.9 and c.z < 0.01) or (n.z > 0.9 and c.z > H - 0.01):
            kill.append(f)
    bmesh.ops.delete(bm, geom=kill, context="FACES")
    bm.to_mesh(me)
    bm.free()


FOCUS = Vector((-0.2, 5.6, 0.8))


def join_static():
    objs = [o for o in coll("STATIC").objects if o.type == "MESH"]
    for o in objs:
        for uvl in list(o.data.uv_layers)[1:]:
            o.data.uv_layers.remove(uvl)
        o.data.uv_layers[0].name = "UVMap"
        if o.name.startswith(("wall_", "floor", "ceiling", "stairwell_wall")):
            prune_hidden_faces(o)
    # per-object lightmap UVs, scaled by how much screen time the object gets
    for o in objs:
        lm = o.data.uv_layers.new(name="Lightmap")
        o.data.uv_layers.active = lm
        bpy.ops.object.select_all(action="DESELECT")
        o.select_set(True)
        bpy.context.view_layer.objects.active = o
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=0.0, area_weight=0.0,
                                 scale_to_bounds=False, correct_aspect=True)
        bpy.ops.object.mode_set(mode="OBJECT")
        # smart_project normalises each object to 0..1: restore world scale, then weight
        area = sum(p.area for p in o.data.polygons) * (o.matrix_world.median_scale ** 2)
        uv_area = 0.0
        uvd = o.data.uv_layers["Lightmap"].data
        for p in o.data.polygons:
            pts = [uvd[i].uv for i in p.loop_indices]
            a2 = 0.0
            for k in range(1, len(pts) - 1):
                e1, e2 = pts[k] - pts[0], pts[k + 1] - pts[0]
                a2 += abs(e1.x * e2.y - e1.y * e2.x) / 2
            uv_area += a2
        center = sum((o.matrix_world @ v.co for v in o.data.vertices), Vector()) / max(1, len(o.data.vertices))
        dist = (center - FOCUS).length
        weight = 3.2 if dist < 1.2 else (2.0 if dist < 2.2 else 1.0)
        if o.name.startswith(("joist", "duct", "ceiling", "step_", "stairwell", "handrail", "rail_bracket", "pipe")):
            weight = 0.45
        k = math.sqrt(area / max(uv_area, 1e-9)) * math.sqrt(weight)
        for d in uvd:
            d.uv = d.uv * k
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join()
    room = bpy.context.view_layer.objects.active
    room.name = "Room_Static"
    me = room.data
    me.uv_layers.active = me.uv_layers["Lightmap"]
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.select_all(action="SELECT")
    bpy.ops.uv.pack_islands(margin=0.002, rotate=True, scale=True)
    bpy.ops.object.mode_set(mode="OBJECT")
    me.uv_layers["UVMap"].active_render = True
    return room


def _gauss_blur(x, sigma):
    r = int(math.ceil(sigma * 3))
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma) ** 2)
    k /= k.sum()
    pad = np.pad(x, r, mode="edge")
    tmp = np.apply_along_axis(lambda m: np.convolve(m, k, mode="valid"), 1, pad)
    return np.apply_along_axis(lambda m: np.convolve(m, k, mode="valid"), 0, tmp)


def pack_lightmap(res=None):
    """Pack cached bakes -> public/models/lightmap.png (RGBA = lamp, violet, screen, ambient)."""
    import json
    from PIL import Image
    groups = ("lamp", "violet", "screen", "ambient")
    ch = {g: np.load(os.path.join(CACHE, f"bake_{g}.npy")).mean(axis=2) for g in groups}
    valid = (sum(ch.values()) > 0).astype(np.float32)
    den = _gauss_blur(valid, 1.2)
    scales = {}
    packed = np.zeros(valid.shape + (4,), np.float32)
    for i, g in enumerate(groups):
        c = np.where(valid > 0, _gauss_blur(ch[g] * valid, 1.2) / np.maximum(den, 1e-6), 0)
        s = float(np.percentile(c[c > 0], 99.7)) if (c > 0).any() else 1.0
        scales[g] = s
        packed[..., i] = np.sqrt(np.clip(c / s, 0, 1))
    # dilate into empty texels so mip/bilinear sampling never pulls black from the gutter
    for _ in range(6):
        empty = valid == 0
        if not empty.any():
            break
        acc = np.zeros_like(packed); cnt = np.zeros(valid.shape, np.float32)
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            sh_v = np.roll(valid, (dy, dx), (0, 1)); sh_p = np.roll(packed, (dy, dx), (0, 1))
            acc += sh_p * sh_v[..., None]; cnt += sh_v
        fill = empty & (cnt > 0)
        packed[fill] = acc[fill] / cnt[fill][:, None]
        valid = np.where(fill, 1.0, valid)
    packed = np.flipud(packed)
    Image.fromarray(np.uint8(np.clip(packed, 0, 1) * 255 + 0.5), "RGBA").save(os.path.join(OUT_MODELS, "lightmap.png"))
    with open(os.path.join(OUT_MODELS, "lightmap.json"), "w") as f:
        json.dump({"channels": list(groups), "scale": scales, "encoding": "sqrt",
                   "colors": {"lamp": LAMP_RGB, "violet": VIOLET_RGB, "screen": SCREEN_RGB, "ambient": STAIR_RGB}}, f, indent=2)
    print("packed lightmap", scales)


def stage_bake():
    bpy.ops.wm.open_mainfile(filepath=BLEND)
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = 48 if QUICK else 192
    sc.cycles.use_denoising = False
    sc.cycles.max_bounces = 6
    sc.cycles.diffuse_bounces = 4
    sc.render.threads_mode = "AUTO"
    room = join_static()
    res = 1024 if QUICK else 2048
    # emissive meshes must not double the lights during bakes; Barry stays visible (contact shadow)
    for o in coll("EMISSIVE").objects:
        o.hide_render = True
    lights = {o.name: o for o in coll("LIGHTS").objects}
    channels = {}
    for group in ("lamp", "violet", "screen", "ambient"):
        im = bpy.data.images.new(f"bake_{group}", res, res, float_buffer=True)
        for m in room.data.materials:
            nt = m.node_tree
            for n in [n for n in nt.nodes if n.name.startswith("BAKE_")]:
                nt.nodes.remove(n)
            uvn = nt.nodes.new("ShaderNodeUVMap"); uvn.uv_map = "Lightmap"; uvn.name = "BAKE_uv"
            tn = nt.nodes.new("ShaderNodeTexImage"); tn.image = im; tn.name = "BAKE_img"
            nt.links.new(uvn.outputs["UV"], tn.inputs["Vector"])
            nt.nodes.active = tn
        for name, o in lights.items():
            o.hide_render = o["group"] != group
        sc.world.node_tree.nodes["Background"].inputs["Strength"].default_value = 1.0 if group == "ambient" else 0.0
        bpy.ops.object.select_all(action="DESELECT")
        room.select_set(True)
        bpy.context.view_layer.objects.active = room
        print("baking", group, flush=True)
        bpy.ops.object.bake(type="DIFFUSE", pass_filter={"DIRECT", "INDIRECT"}, margin=6, use_clear=True)
        px = np.array(im.pixels[:], dtype=np.float32).reshape(res, res, 4)[..., :3]
        channels[group] = px.mean(axis=2)  # irradiance luminance (light colour applied at runtime)
        np.save(os.path.join(CACHE, f"bake_{group}.npy"), px)
    pack_lightmap(res)
    # remove bake nodes, save baked blend for export
    for m in room.data.materials:
        for n in [n for n in m.node_tree.nodes if n.name.startswith("BAKE_")]:
            m.node_tree.nodes.remove(n)
    for o in coll("EMISSIVE").objects:
        o.hide_render = False
    for o in lights.values():
        o.hide_render = False
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(CACHE, "studio_baked.blend"))



GUITAR_BOX = ((2.05, 2.75, 0.0), (2.6, 3.65, 1.3))


def post_bake_fixes():
    """Art-direction fixes that don't change lightmap UVs (so no re-bake is needed)."""
    def untexture(name, color, rough=None, metal=None):
        m = bpy.data.materials.get(name)
        if not m:
            return
        nt = m.node_tree
        bsdf = nt.nodes.get("Principled BSDF")
        for n in [n for n in nt.nodes if n.type in ("TEX_IMAGE", "NORMAL_MAP")]:
            nt.nodes.remove(n)
        bsdf.inputs["Base Color"].default_value = (*color, 1)
        if rough is not None:
            bsdf.inputs["Roughness"].default_value = rough
        if metal is not None:
            bsdf.inputs["Metallic"].default_value = metal
    untexture("paint_trim", (0.075, 0.07, 0.078), rough=0.62)
    untexture("duct", (0.3, 0.3, 0.32), rough=0.42, metal=1.0)
    scr = bpy.data.materials.get("screen")
    if scr:
        scr.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.05
    # remove the guitar (its faces only — the rest of the lightmap atlas is untouched)
    room = bpy.data.objects.get("Room_Static")
    if room:
        (x0, y0, z0), (x1, y1, z1) = GUITAR_BOX
        bm = bmesh.new()
        bm.from_mesh(room.data)
        kill = [f for f in bm.faces if all(x0 < v.co.x < x1 and y0 < v.co.y < y1 and z0 - 0.001 < v.co.z < z1 for v in f.verts)
                and not any(abs(v.co.x - W1) < 0.01 for v in f.verts)]
        bmesh.ops.delete(bm, geom=kill, context="FACES")
        bm.to_mesh(room.data)
        bm.free()
        print("post-bake: removed", len(kill), "guitar faces")
    # cameras follow SHOTS
    for key, (pos, tgt, fov) in SHOTS.items():
        ob = bpy.data.objects.get("CAM_" + key)
        if ob:
            ob.location = pos
            ob.rotation_euler = (Vector(tgt) - Vector(pos)).to_track_quat("-Z", "Y").to_euler()
            ob.data.angle_y = math.radians(fov)
            ob.data.dof.focus_distance = (Vector((-0.27, 5.7, 0.86)) - Vector(pos)).length
    # reload textures from disk (e.g. a regenerated, dustier blanket)
    for im in bpy.data.images:
        if im.filepath:
            im.reload()

# ================================================================ render stage
def stage_render():
    path = os.path.join(CACHE, "studio_baked.blend")
    bpy.ops.wm.open_mainfile(filepath=path if os.path.exists(path) else BLEND)
    post_bake_fixes()
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = 32 if QUICK else 160
    sc.cycles.use_denoising = True
    sc.cycles.max_bounces = 6
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "AgX - Medium High Contrast"
    sc.view_settings.exposure = 1.7
    sc.world.node_tree.nodes["Background"].inputs["Strength"].default_value = 1.0
    for o in bpy.data.objects:
        if o.name == "screen_area":
            o.hide_render = True
    sc.render.image_settings.file_format = "JPEG"
    sc.render.image_settings.quality = 88
    jobs = [("overview", (1920, 1080)), ("overview_portrait", (1080, 2340))]
    if "--debug" in sys.argv:
        jobs = [(k, (1280, 720)) for k in DEBUG_SHOTS] + jobs
    only = [a.split("=", 1)[1] for a in sys.argv if a.startswith("--only=")]
    if only:
        jobs = [j for j in jobs if j[0] in only]
    for key, (w, h) in jobs:
        if QUICK:
            w, h = w // 3, h // 3
        sc.render.resolution_x, sc.render.resolution_y = w, h
        sc.render.resolution_percentage = 100
        sc.camera = bpy.data.objects["CAM_" + key]
        sc.render.filepath = os.path.join(OUT_STILLS if not QUICK else CACHE, f"{key}.jpg")
        bpy.ops.render.render(write_still=True)
        print("rendered", sc.render.filepath, flush=True)


# ================================================================ export stage
def bake_barry_textures():
    """Bake Barry's procedural fur colour into images so it survives glTF export."""
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.samples = 4
    for name, res in (("Barry_Body", 1024), ("Barry_Head", 512), ("Barry_Tail", 256)):
        ob = bpy.data.objects[name]
        me = ob.data
        if not me.uv_layers:
            me.uv_layers.new(name="UVMap")
        bpy.ops.object.select_all(action="DESELECT")
        ob.select_set(True)
        bpy.context.view_layer.objects.active = ob
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.01)
        bpy.ops.object.mode_set(mode="OBJECT")
        im = bpy.data.images.new(f"{name}_albedo", res, res)
        # per-object copy of fur material so each gets its own texture
        m = me.materials[0].copy(); m.name = f"{name}_fur"
        me.materials[0] = m
        nt = m.node_tree
        bsdf = nt.nodes["Principled BSDF"]
        color_src = bsdf.inputs["Base Color"].links[0].from_socket
        em = nt.nodes.new("ShaderNodeEmission")
        out = nt.nodes["Material Output"]
        nt.links.new(color_src, em.inputs["Color"])
        nt.links.new(em.outputs[0], out.inputs["Surface"])
        tn = nt.nodes.new("ShaderNodeTexImage"); tn.image = im; nt.nodes.active = tn
        bpy.ops.object.bake(type="EMIT", margin=4)
        # rewire: baked image -> base color, BSDF -> output
        for n in list(nt.nodes):
            if n.type not in ("BSDF_PRINCIPLED", "OUTPUT_MATERIAL") and n != tn:
                nt.nodes.remove(n)
        nt.links.new(tn.outputs["Color"], bsdf.inputs["Base Color"])
        nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
        im.filepath_raw = os.path.join(CACHE, f"{name}_albedo.png")
        im.file_format = "PNG"
        im.save()


def stage_export():
    bpy.ops.wm.open_mainfile(filepath=os.path.join(CACHE, "studio_baked.blend"))
    post_bake_fixes()
    bake_barry_textures()
    # studio: Room_Static + EMISSIVE objects + hotspot markers
    def export(path, objs):
        bpy.ops.object.select_all(action="DESELECT")
        for o in objs:
            o.select_set(True)
        bpy.ops.export_scene.gltf(filepath=path, export_format="GLB", use_selection=True, export_apply=True,
                                  export_texcoords=True, export_normals=True, export_tangents=False,
                                  export_materials="EXPORT", export_image_format="AUTO", export_yup=True,
                                  export_cameras=False, export_lights=False, export_extras=True)
    studio = [bpy.data.objects["Room_Static"]] + [o for o in coll("EMISSIVE").objects]
    export(os.path.join(OUT_MODELS, "studio.raw.glb"), studio)
    barry = [o for o in coll("BARRY").objects]
    export(os.path.join(OUT_MODELS, "barry.raw.glb"), barry)
    # print reference positions for the web app (three.js coords: x, z, -y)
    for nm in ("Lamp_Bulb", "Laptop_Screen", "violet_strip", "Barry", "corkboard"):
        o = bpy.data.objects.get(nm)
        if o:
            if o.type == "MESH":
                c = sum((o.matrix_world @ v.co for v in o.data.vertices), Vector()) / len(o.data.vertices)
            else:
                c = o.matrix_world.translation
            print(f"REF {nm}: three=({c.x:.3f}, {c.z:.3f}, {-c.y:.3f})")
    lamp = bpy.data.objects["lamp_spot"]
    d = lamp.matrix_world.to_3x3() @ Vector((0, 0, -1))
    print(f"REF lamp_dir three=({d.x:.3f}, {d.z:.3f}, {-d.y:.3f})")


if __name__ == "__main__":
    if STAGE in ("build", "all"):
        stage_build()
    if STAGE in ("bake", "all"):
        stage_bake()
    if STAGE == "pack":
        pack_lightmap()
    if STAGE in ("render", "all"):
        stage_render()
    if STAGE in ("export", "all"):
        stage_export()
