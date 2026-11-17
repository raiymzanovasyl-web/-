"""Lighting, cameras and renders.  python render.py <out_dir> [--quick] [shots...]"""
import math, os, sys
import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build

args = [a for a in sys.argv[1:] if not a.startswith("--")]
OUT = args[0] if args else os.path.join(HERE, "renders")
SHOTS = args[1:] or ["hero", "face", "anatomy_front", "anatomy_side", "anatomy_back", "hands"]
QUICK = "--quick" in sys.argv


def light(name, kind, loc, target, energy, color, size=0.5, spot=None):
    L = bpy.data.lights.new(name, kind); L.energy = energy; L.color = color
    if kind == 'AREA':
        L.size = size
    if kind == 'SPOT':
        L.spot_size = math.radians(spot or 40); L.spot_blend = 0.6; L.shadow_soft_size = size
    o = bpy.data.objects.new(name, L); bpy.context.scene.collection.objects.link(o)
    o.location = loc
    o.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    return o


def stage():
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'
    sc.cycles.samples = 32 if QUICK else 160
    sc.cycles.use_denoising = True
    sc.cycles.max_bounces = 6
    sc.view_settings.view_transform = 'AgX'
    sc.view_settings.look = 'AgX - Punchy'
    w = bpy.data.worlds.new("Dark"); sc.world = w; w.use_nodes = True
    w.node_tree.nodes["Background"].inputs[0].default_value = (0.004, 0.005, 0.006, 1)
    # wet concrete floor
    bpy.ops.mesh.primitive_plane_add(size=12, location=(0, 0, 0))
    floor = bpy.context.object; floor.name = "Floor"
    m, nt, b = build.nodes_mat("Concrete")
    tex = build.N(nt, "ShaderNodeTexCoord")
    nz = build.N(nt, "ShaderNodeTexNoise", Scale=4.0, Detail=12.0, Roughness=0.7)
    build.L(nt, tex.outputs["Object"], nz.inputs["Vector"])
    cr = build.ramp(nt, [(0.3, (0.018, 0.018, 0.017)), (0.7, (0.05, 0.048, 0.045))])
    build.L(nt, nz.outputs["Fac"], cr.inputs["Fac"]); build.L(nt, cr.outputs["Color"], b.inputs["Base Color"])
    wet = build.ramp(nt, [(0.45, (0.12, 0.12, 0.12)), (0.55, (0.75, 0.75, 0.75))])
    nz2 = build.N(nt, "ShaderNodeTexNoise", Scale=1.3, Detail=4.0)
    build.L(nt, tex.outputs["Object"], nz2.inputs["Vector"])
    build.L(nt, nz2.outputs["Fac"], wet.inputs["Fac"]); build.L(nt, wet.outputs["Color"], b.inputs["Roughness"])
    floor.data.materials.append(m)
    # lights: hard cold top, red rims behind, a sick green bounce from below
    light("Key_Top", 'SPOT', (-0.35, -1.1, 3.4), (0, 0, 1.55), 900, (0.80, 0.88, 1.0), size=0.12, spot=34)
    light("Rim_Red_L", 'SPOT', (-1.2, 1.6, 2.6), (0, 0, 1.45), 700, (1.0, 0.10, 0.06), size=0.1, spot=24)
    light("Rim_Red_R", 'SPOT', (1.3, 1.5, 2.2), (0, 0, 1.4), 520, (1.0, 0.16, 0.08), size=0.1, spot=24)
    light("Under_Green", 'AREA', (0.2, -0.9, 0.15), (0, 0, 1.6), 22, (0.45, 1.0, 0.45), size=0.8)
    light("Studio_Key", 'AREA', (-2.5, -3.0, 3.0), (0, 0, 1.1), 900, (1, 1, 1), size=2.5)
    light("Studio_Fill", 'AREA', (3.0, -1.5, 2.0), (0, 0, 1.1), 350, (1, 1, 1), size=2.5)
    light("Studio_Back", 'AREA', (0.5, 3.5, 3.0), (0, 0, 1.3), 600, (1, 1, 1), size=2.0)
    light("Face_Fill", 'AREA', (0.6, -1.2, 1.7), (0, 0, 1.8), 6, (0.9, 0.95, 1.0), size=0.3)


def camera(loc, target, lens):
    cam = bpy.context.scene.camera
    if cam is None:
        cam = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera"))
        bpy.context.scene.collection.objects.link(cam); bpy.context.scene.camera = cam
    cam.location = loc; cam.data.lens = lens
    cam.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    cam.data.dof.use_dof = False
    return cam


def studio(on):
    for o in bpy.data.objects:
        if o.type == 'LIGHT':
            o.hide_render = o.name.startswith("Studio") != on
    bpy.data.objects["Floor"].hide_render = on
    bpy.context.scene.world.node_tree.nodes["Background"].inputs[0].default_value = (0.18, 0.18, 0.19, 1) if on else (0.004, 0.005, 0.006, 1)


def show_costume(on, clay=False):
    for name in ("Costume",):
        bpy.data.collections[name].hide_render = not on
    vl = bpy.context.view_layer
    vl.material_override = bpy.data.materials.get("Clay") if clay else None
    for n in ("Hair", "Gums"):
        o = bpy.data.objects.get(n)
        if o:
            o.hide_render = clay


def clay_mat():
    m, nt, b = build.nodes_mat("Clay")
    b.inputs["Base Color"].default_value = (0.55, 0.50, 0.46, 1)
    b.inputs["Roughness"].default_value = 0.5
    return m


def shoot(name, res, cam):
    sc = bpy.context.scene
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.filepath = os.path.join(OUT, name + ".png")
    camera(*cam)
    bpy.ops.render.render(write_still=True)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    build.build_scene()
    stage(); clay_mat()
    k = 0.5 if QUICK else 1.0
    R = lambda w, h: (int(w * k), int(h * k))
    for s in SHOTS:
        if s == "hero":
            studio(False); show_costume(True); shoot(s, R(1200, 1600), ((0.95, -2.9, 1.35), (0, 0, 1.08), 42))
        elif s == "face":
            studio(False); show_costume(True); shoot(s, R(1400, 1400), ((0.16, -0.62, 1.78), (0, -0.04, 1.80), 80))
        elif s.startswith("anatomy"):
            studio(True); show_costume(False, clay=True)
            ang = {"anatomy_front": 0, "anatomy_side": 90, "anatomy_back": 180}[s]
            a = math.radians(ang)
            shoot(s, R(900, 1600), ((math.sin(a) * 4.4, -math.cos(a) * 4.4, 1.0), (0, 0, 0.98), 50))
        elif s == "hands":
            studio(False); show_costume(True)
            from anatomy import arm_points
            _, _, w, d = arm_points(1); t = w + d * 0.13
            shoot(s, R(1200, 900), (t + Vector((0.10, -0.62, 0.12)), t, 60))
        elif s == "torso":
            studio(False); show_costume(True); shoot(s, R(1200, 1200), ((0.35, -1.25, 1.45), (0, 0, 1.38), 55))
    print("done")
