"""Game-ready export: decimated meshes, UVs, textures baked from the high-poly sculpt,
a humanoid skeleton (Mixamo-style names) with automatic weights, and a .glb.
Run:  python export_game.py"""
import math, os, sys
import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build
import anatomy as A

OUT = os.path.join(HERE, "game")
# target triangle counts per object (a mid-range game character ~ 60k tris total)
BUDGET = {"Clown_Body": 30000, "Shirt": 9000, "Pants": 7000, "Ruff": 5000, "Cuff_L": 1500, "Cuff_R": 1500,
          "Shoe_L": 2500, "Shoe_R": 2500, "Teeth": None, "Nails": None, "Eye_L": 600, "Eye_R": 600, "Nose": 600}
TEX = {"Clown_Body": 2048, "Shirt": 1024, "Pants": 1024, "Ruff": 1024, "Shoe_L": 512, "Shoe_R": 512}


def tri_count(o):
    return sum(len(p.vertices) - 2 for p in o.data.polygons)


def select_only(objs, active=None):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = active or objs[0]


def make_low(hi, target):
    lo = hi.copy(); lo.data = hi.data.copy(); lo.name = hi.name + "_LOD0"
    bpy.context.scene.collection.objects.link(lo)
    select_only([lo])
    for m in list(lo.modifiers):
        bpy.ops.object.modifier_apply(modifier=m.name)
    if target and tri_count(lo) > target:
        dec = lo.modifiers.new("dec", 'DECIMATE'); dec.ratio = target / tri_count(lo)
        bpy.ops.object.modifier_apply(modifier="dec")
    bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.006)
    bpy.ops.object.mode_set(mode='OBJECT')
    return lo


def bake(hi, lo, size):
    sc = bpy.context.scene
    img_c = bpy.data.images.new(lo.name + "_BaseColor", size, size)
    img_n = bpy.data.images.new(lo.name + "_Normal", size, size); img_n.colorspace_settings.name = 'Non-Color'
    m, nt, b = build.nodes_mat(lo.name.replace("_LOD0", "") + "_Game")
    tc = nt.nodes.new("ShaderNodeTexImage"); tc.image = img_c
    tn = nt.nodes.new("ShaderNodeTexImage"); tn.image = img_n
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nt.links.new(tc.outputs[0], b.inputs["Base Color"])
    nt.links.new(tn.outputs[0], nm.inputs["Color"]); nt.links.new(nm.outputs[0], b.inputs["Normal"])
    src = hi.active_material
    b.inputs["Roughness"].default_value = 0.6 if "Body" in lo.name else 0.85
    lo.data.materials.clear(); lo.data.materials.append(m)
    select_only([hi, lo], active=lo)
    bk = sc.render.bake
    bk.use_selected_to_active = True; bk.cage_extrusion = 0.012; bk.max_ray_distance = 0.03
    bk.margin = 8
    for img, kind in ((img_c, 'DIFFUSE'), (img_n, 'NORMAL')):
        nt.nodes.active = tc if img is img_c else tn
        if kind == 'DIFFUSE':
            bk.use_pass_direct = False; bk.use_pass_indirect = False; bk.use_pass_color = True
        bpy.ops.object.bake(type=kind)
        img.filepath_raw = os.path.join(OUT, "textures", img.name + ".png"); img.file_format = 'PNG'; img.save()
        img.pack()


BONES = []


def bone(arm, name, head, tail, parent=None):
    b = arm.edit_bones.new(name); b.head = Vector(head); b.tail = Vector(tail)
    if parent:
        b.parent = arm.edit_bones[parent]; b.use_connect = (b.parent.tail - b.head).length < 1e-4
    BONES.append(name)
    return name


def skeleton():
    arm = bpy.data.armatures.new("Clown_Rig"); rig = bpy.data.objects.new("Clown_Rig", arm)
    bpy.context.scene.collection.objects.link(rig)
    select_only([rig]); bpy.ops.object.mode_set(mode='EDIT')
    bone(arm, "Hips", (0, 0.01, 0.98), (0, 0.01, 1.10))
    bone(arm, "Spine", (0, 0.01, 1.10), (0, 0.01, 1.25), "Hips")
    bone(arm, "Spine1", (0, 0.01, 1.25), (0, 0.01, 1.42), "Spine")
    bone(arm, "Spine2", (0, 0.01, 1.42), (0, 0.01, 1.58), "Spine1")
    bone(arm, "Neck", (0, 0.01, 1.58), (0, 0.005, 1.72), "Spine2")
    bone(arm, "Head", (0, 0.005, 1.72), (0, 0.005, 1.95), "Neck")
    bone(arm, "Jaw", (0, 0.000, 1.765), (0, -0.068, 1.712), "Head")
    for sx, side in ((1, "Left"), (-1, "Right")):
        s, e, w, d = A.arm_points(sx)
        bone(arm, side + "Shoulder", (sx * 0.035, 0.0, 1.555), s, "Spine2")
        bone(arm, side + "Arm", s, e, side + "Shoulder")
        bone(arm, side + "ForeArm", e, w, side + "Arm")
        bone(arm, side + "Hand", w, w + d * 0.095, side + "ForeArm")
        for fi, fname in enumerate(("Thumb", "Index", "Middle", "Ring", "Pinky")):
            J = A.JOINTS[(sx, fi)]
            par = side + "Hand"
            for k in range(3):
                par = bone(arm, f"{side}Hand{fname}{k + 1}", J[k], J[k + 1], par)
        h = Vector((A.HIP[0] * sx, A.HIP[1], A.HIP[2])); kn = Vector((A.KNEE[0] * sx, A.KNEE[1], A.KNEE[2]))
        an = Vector((A.ANKLE[0] * sx, A.ANKLE[1], A.ANKLE[2]))
        bone(arm, side + "UpLeg", h, kn, "Hips")
        bone(arm, side + "Leg", kn, an, side + "UpLeg")
        bone(arm, side + "Foot", an, an + Vector((0, -0.12, -0.07)), side + "Leg")
        bone(arm, side + "ToeBase", an + Vector((0, -0.12, -0.07)), an + Vector((0, -0.30, -0.07)), side + "Foot")
    bpy.ops.object.mode_set(mode='OBJECT')
    return rig


def bind(rig, objs, rigid=None):
    for o in objs:
        if rigid and o.name.split("_LOD0")[0] in rigid:
            vg = o.vertex_groups.new(name=rigid[o.name.split("_LOD0")[0]])
            vg.add(list(range(len(o.data.vertices))), 1.0, 'REPLACE')
            mod = o.modifiers.new("Armature", 'ARMATURE'); mod.object = rig; o.parent = rig
            continue
        select_only([o, rig], active=rig)
        bpy.ops.object.parent_set(type='ARMATURE_AUTO')


if __name__ == "__main__":
    os.makedirs(os.path.join(OUT, "textures"), exist_ok=True)
    build.build_scene()
    sc = bpy.context.scene
    sc.render.engine = 'CYCLES'; sc.cycles.samples = 4; sc.cycles.device = 'CPU'
    # hair: curves -> thin mesh strands
    hair = bpy.data.objects["Hair"]; hair.data.bevel_resolution = 0
    select_only([hair]); bpy.ops.object.convert(target='MESH'); hair.name = "Hair_LOD0"
    lows = [hair]
    for name, target in BUDGET.items():
        hi = bpy.data.objects[name]
        lo = make_low(hi, target)
        if name in TEX:
            bake(hi, lo, TEX[name])
        lows.append(lo)
    for o in list(bpy.data.objects):
        if o.type == 'MESH' and not o.name.endswith("_LOD0") or o.type == 'LIGHT':
            if o.name.startswith("Pompom"):
                lo = make_low(o, 400); lows.append(lo)
            bpy.data.objects.remove(o)
    rig = skeleton()
    rigid = {"Eye_L": "Head", "Eye_R": "Head", "Nose": "Head", "Teeth": "Head", "Hair": "Head"}
    bind(rig, lows, rigid)
    total = sum(tri_count(o) for o in lows)
    select_only(lows + [rig], active=rig)
    bpy.ops.export_scene.gltf(filepath=os.path.join(OUT, "clown.glb"), use_selection=True,
                              export_format='GLB', export_apply=True, export_skins=True)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "clown_game.blend"), compress=True)
    print("TRIS", total, "BONES", len(BONES))
