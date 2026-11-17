"""Render shots of a saved clown .blend.  python look.py file.blend outdir samples scale shot..."""
import math, os, sys
import bpy
from mathutils import Vector
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
blend, out, samples, scale = sys.argv[1], sys.argv[2], int(sys.argv[3]), float(sys.argv[4])
shots = sys.argv[5:]
bpy.ops.wm.open_mainfile(filepath=blend)
sys.argv = ["render.py", out]
import render as R
import build as B
R.OUT = out; os.makedirs(out, exist_ok=True)
if not bpy.data.objects.get("Floor"):
    R.stage()
sc = bpy.context.scene; sc.cycles.samples = samples
if not bpy.data.materials.get("Clay"):
    R.clay_mat()


def studio(on):
    for o in bpy.data.objects:
        if o.type == 'LIGHT':
            o.hide_render = o.name.startswith("Studio") != on
    bpy.data.objects["Floor"].hide_render = on
    sc.world.node_tree.nodes["Background"].inputs[0].default_value = (0.20, 0.20, 0.21, 1) if on else (0.004, 0.005, 0.006, 1)


S = lambda w, h: (int(w * scale), int(h * scale))
CAM = {
    "front": ((0.9, -3.6, 1.30), (0, 0, 1.00), 40, (1100, 1400)),
    "side": ((3.6, -0.6, 1.25), (0, 0, 1.00), 40, (1100, 1400)),
    "back": ((-1.4, 3.4, 1.35), (0, 0, 1.00), 40, (1100, 1400)),
    "face": ((0.30, -0.95, 1.82), (0, -0.06, 1.79), 70, (1200, 1200)),
    "face_front": ((0.0, -1.0, 1.80), (0, -0.06, 1.79), 70, (1200, 1200)),
    "torso": ((0.6, -1.9, 1.35), (0, -0.05, 1.25), 45, (1200, 1300)),
    "legs": ((0.8, -2.2, 0.55), (0, 0, 0.55), 45, (1200, 1300)),
    "hero": ((0.85, -2.8, 1.10), (0, -0.05, 1.15), 36, (1200, 1500)),
    "hero_face": ((0.22, -1.05, 1.62), (0, -0.10, 1.72), 65, (1200, 1200)),
}
for s in shots:
    name, mode = (s.split(":") + ["dark"])[:2]
    loc, tgt, lens, res = CAM[name]
    studio(mode in ("clay", "studio", "product"))
    if mode == "product":
        if not bpy.data.objects.get("Backdrop"):
            bpy.ops.mesh.primitive_plane_add(size=14, location=(0, 0, 0.001))
            bd = bpy.context.object; bd.name = "Backdrop"
            m, nt, b = B.nodes_mat("Backdrop"); b.inputs["Base Color"].default_value = (0.018, 0.018, 0.019, 1)
            b.inputs["Roughness"].default_value = 0.9; bd.data.materials.append(m)
        bpy.data.objects["Backdrop"].hide_render = False
        sc.world.node_tree.nodes["Background"].inputs[0].default_value = (0.008, 0.008, 0.009, 1)
    elif bpy.data.objects.get("Backdrop"):
        bpy.data.objects["Backdrop"].hide_render = True
    bpy.context.view_layer.material_override = bpy.data.materials["Clay"] if mode == "clay" else None
    R.shoot(f"{name}_{mode}", S(*res), (loc, tgt, lens))
