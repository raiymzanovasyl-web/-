"""Massive clown: high-poly sculpt (SDF) + costume, then a game LOD (Quadriflow quads, baked maps, rig).
python brute.py preview <out>      quick look at the sculpt
python brute.py full                build high + low poly, bake, rig, export, render"""
import math, os, random, sys
import numpy as np
import bpy, bmesh
from mathutils import Vector, Quaternion

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build as B                      # materials, Field.shape / displace / shell, torus_frill, halfspace
import brute_anatomy as A
from sdf import Field, front_y
from meshing import mesh_object

MODE = sys.argv[1] if len(sys.argv) > 1 else "preview"
QUICK = MODE == "preview"
random.seed(4)


# ================================================================== makeup
def paint(o):
    me = o.data; n = len(me.vertices)
    co = np.empty(n * 3, np.float32); me.vertices.foreach_get("co", co); co = co.reshape(-1, 3)
    x, y, z = co[:, 0], co[:, 1], co[:, 2]
    skin = np.array([0.52, 0.45, 0.40]); white = np.array([0.88, 0.87, 0.82])
    col = np.tile(skin, (n, 1)); paint_a = np.zeros(n)
    w = np.clip((z - 1.62) / 0.05, 0, 1) * np.clip((0.07 - y) / 0.05, 0, 1)
    w = np.maximum(w, np.clip((z - 1.75) / 0.03, 0, 1))
    col = col * (1 - w[:, None]) + white * w[:, None]; paint_a = np.maximum(paint_a, w)
    # sooty smudge around the eyes, running down in streaks
    for sx in (1, -1):
        ex, ez = sx * 0.036, 1.810
        r = np.sqrt(((x - ex) / 0.034) ** 2 + ((z - ez) / 0.030) ** 2)
        m = np.clip((1.0 - r) / 0.25, 0, 1) * (y < -0.06)
        for k in range(5):
            dx = ex + sx * (-0.016 + 0.008 * k)
            streak = np.clip(1 - np.abs(x - dx) / 0.0022, 0, 1) * (z < ez) * (z > ez - 0.03 - 0.012 * (k % 3)) * (y < -0.06)
            m = np.maximum(m, streak * 0.9)
        col = col * (1 - m[:, None]) + np.array([0.035, 0.03, 0.035]) * m[:, None]
    # blood-red mouth, painted far past the lips
    r = np.sqrt((x / 0.090) ** 2 + ((z - 1.706) / 0.046) ** 2)
    rough = np.array([np.sin(px * 160) * 0.05 + np.sin(pz * 210) * 0.04 for px, pz in zip(x, z)]) if n < 0 else 0
    m = np.clip((1.0 - r) / 0.12, 0, 1) * (y < -0.04)
    col = col * (1 - m[:, None]) + np.array([0.33, 0.012, 0.016]) * m[:, None]
    # dirt on hands and forearms
    for p, dirn, inward, _ in A.NAILS:
        dd = np.linalg.norm(co - np.array(p), axis=1)
        t = np.clip((0.05 - dd) / 0.05, 0, 1) * 0.6
        col = col * (1 - t[:, None]) + np.array([0.20, 0.12, 0.09]) * t[:, None]
    attr = me.color_attributes.new("makeup", 'FLOAT_COLOR', 'POINT')
    attr.data.foreach_set("color", np.concatenate([col, paint_a[:, None]], 1).astype(np.float32).ravel())


# ================================================================== parts
def rounded_box(name, items, mat, coll, bevel=0.35):
    """items: (centre, x-axis, z-axis, (w, h, d)) boxes merged into one mesh, corners bevelled."""
    bm = bmesh.new()
    for c, ax, az, (w, h, d) in items:
        ay = az.cross(ax).normalized()
        geom = bmesh.ops.create_cube(bm, size=1.0)
        M = np.array([[ax.x * w, ay.x * d, az.x * h], [ax.y * w, ay.y * d, az.y * h], [ax.z * w, ay.z * d, az.z * h]])
        for v in geom["verts"]:
            p = M @ np.array(v.co)
            v.co = Vector(p) + c
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new(name, me); coll.objects.link(o)
    bv = o.modifiers.new("bevel", 'BEVEL'); bv.width = bevel; bv.offset_type = 'PERCENT'; bv.width_pct = 35; bv.segments = 3
    o.modifiers.new("sub", 'SUBSURF').levels = 1
    me.materials.append(mat); me.shade_smooth()
    return o


def teeth(coll, mats):
    items = []
    rnd = random.Random(2)
    for row, sgn, H in (("upper", 1, 0.023), ("lower", -1, 0.017)):
        pts = A.MOUTH[row]
        for i, p in enumerate(pts):
            nxt = pts[min(i + 1, len(pts) - 1)]; prv = pts[max(i - 1, 0)]
            tangent = (nxt - prv).normalized()
            out = Vector((p.x, p.y + 0.06, 0)).normalized() * -1 if abs(p.x) > 1e-4 else Vector((0, -1, 0))
            out = Vector((0, -1, 0)).lerp(Vector((p.x, -0.02, 0)).normalized(), min(1, abs(p.x) / 0.05)).normalized()
            centre = abs(i - (len(pts) - 1) / 2) / ((len(pts) - 1) / 2)
            w = (pts[1] - pts[0]).length * 0.92
            h = H * (1.0 - 0.25 * centre) * rnd.uniform(0.9, 1.1)
            tilt = Quaternion(tangent, math.radians(rnd.uniform(-7, 7)))
            az = tilt @ Vector((0, 0, 1)); ax = tilt @ tangent
            if rnd.random() < 0.08:
                continue                                                   # a gap
            c = p + Vector((0, 0, -sgn * h * 0.18))
            items.append((c, ax, az, (w * 0.94, h, 0.011)))
    t = rounded_box("Teeth", items, mats["teeth"], coll)
    # gums above the upper and below the lower teeth
    cu = bpy.data.curves.new("Gums", 'CURVE'); cu.dimensions = '3D'; cu.bevel_depth = 0.0058; cu.bevel_resolution = 3
    for row, dz in (("upper", 0.0105), ("lower", -0.0085)):
        sp = cu.splines.new('POLY'); pts = A.MOUTH[row]; sp.points.add(len(pts) - 1)
        for k, p in enumerate(pts):
            sp.points[k].co = (p.x, p.y + 0.003, p.z + dz, 1)
    g = bpy.data.objects.new("Gums", cu); coll.objects.link(g); g.data.materials.append(mats["gums"])
    return [t, g]


def face_parts(coll, mats):
    out = []
    for i, (c, r) in enumerate(A.EYES):
        bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, radius=r, location=c)
        e = bpy.context.object; e.name = f"Eye_{'LR'[i]}"; B.link(e, coll)
        bpy.ops.object.shade_smooth(); e.data.materials.append(mats["eye"]); out.append(e)
    bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24, radius=0.034, location=(0, -0.150, 1.768))
    nose = bpy.context.object; nose.name = "Nose"; nose.scale = (1.0, 0.92, 0.95); B.link(nose, coll)
    bpy.ops.object.shade_smooth(); nose.data.materials.append(mats["nose"]); out.append(nose)
    # thick claw nails
    verts, faces = [], []
    for p, dirn, inward, r in A.NAILS:
        base = Vector(p) - dirn * 0.008 - inward * 0.006
        tip = Vector(p) + dirn * 0.020 + inward * 0.008
        u = dirn.cross(inward).normalized(); seg = 8; i0 = len(verts)
        for s in range(seg):
            a = 2 * math.pi * s / seg
            verts.append(base + u * math.cos(a) * r - inward * math.sin(a) * r * 0.55)
        verts.append(tip); verts.append(base - dirn * r * 0.3)
        for s in range(seg):
            faces.append((i0 + s, i0 + (s + 1) % seg, i0 + seg)); faces.append((i0 + (s + 1) % seg, i0 + s, i0 + seg + 1))
    me = bpy.data.meshes.new("Nails"); me.from_pydata([tuple(v) for v in verts], [], faces); me.update()
    nails = bpy.data.objects.new("Nails", me); coll.objects.link(nails); me.materials.append(mats["nails"]); me.shade_smooth()
    out.append(nails)
    return out


def hair(coll, mats):
    Hf = Field((-0.20, -0.10, 1.66), (0.20, 0.20, 2.00), 0.0026 if not QUICK else 0.004)
    rnd = random.Random(8)
    C, R = Vector((0, 0.030, 1.850)), Vector((0.098, 0.112, 0.100))
    for sx in (1, -1):
        for k in range(30):
            th = math.radians(rnd.uniform(-30, 75)); ph = math.radians(rnd.uniform(-8, 30))
            n = Vector((sx * math.cos(ph) * math.cos(th), math.cos(ph) * math.sin(th), math.sin(ph)))
            root = Vector((C.x + R.x * n.x, C.y + R.y * n.y, C.z + R.z * n.z)) - n * 0.008
            d = (n * 0.8 + Vector((sx * 0.5, 0.45, rnd.uniform(0.0, 0.35)))).normalized()
            r = rnd.uniform(0.015, 0.022); p = root
            L = rnd.uniform(0.045, 0.085)
            for s in range(5):
                d = (d + Vector((sx * 0.08, 0.12, rnd.uniform(-0.30, 0.05)))).normalized()
                q = p + d * L / 5
                Hf.cap(p, q, r, r * 0.72, k=0.010 if s == 0 else 0.004)
                p, r = q, r * 0.72
    Hf.displace(lambda x, y, z: 0.0012 * np.sin(900 * (x * 0.3 + y * 0.6 + z)), (-0.2, -0.1, 1.66), (0.2, 0.2, 2.0), band=0.004)
    o = B.field_object(Hf, "Hair", coll, iters=1); o.data.materials.append(mats["hair"])
    return o


def costume(coll, mats, body_F):
    h = 0.0065 if QUICK else 0.0038
    out = []
    P = Field((-0.38, -0.32, 0.10), (0.38, 0.26, 1.22), h)
    P.ell((0, 0.020, 1.020), (0.232, 0.175, 0.135), k=0.05)
    for sx in (1, -1):
        hp, kn, an = (Vector((v[0] * sx, v[1], v[2])) for v in (A.HIP, A.KNEE, A.ANKLE))
        P.cap(hp, kn, 0.150, 0.118, k=0.06)
        P.cap(kn, an + Vector((0, 0, 0.10)), 0.118, 0.098, k=0.05)
        P.ell(an + Vector((0, 0, 0.115)), (0.108, 0.108, 0.055), k=0.04)
    P.shape(B.halfspace((0, 0, 1.100), (0, 0.18, 1)), (-0.5, -0.4, 1.0), (0.5, 0.4, 1.25), k=0.008, neg=True)
    P.shape(B.halfspace((0, 0, 0.175), (0, 0, -1)), (-0.5, -0.4, 0.05), (0.5, 0.4, 0.22), k=0.004, neg=True)
    P.displace(lambda x, y, z: 0.007 * np.sin(48 * z + 6 * np.sin(14 * x)) * np.clip((0.6 - z) / 0.3, 0, 1)
               + 0.004 * np.sin(26 * z + 8 * np.cos(11 * y)) + 0.003 * np.sin(19 * x - 31 * z), (-0.5, -0.4, 0.1), (0.5, 0.4, 1.25))
    pants = B.field_object(P, "Pants", coll); pants.data.materials.append(mats["pants"]); out.append(pants)

    # suspenders: flat straps hugging the chest and back, over the trapezius
    S = Field((-0.30, -0.36, 1.00), (0.30, 0.30, 1.78), h * 0.8)
    for sx in (1, -1):
        path = []
        for z in np.linspace(1.08, 1.55, 9):
            x = sx * (0.095 + 0.03 * (z - 1.08) / 0.47)
            yf = front_y(body_F, x, z, y0=-0.36, y1=0.1)
            path.append(Vector((x, yf - 0.004, z)))
        path += [Vector((sx * 0.135, -0.07, 1.640)), Vector((sx * 0.150, 0.02, 1.690)), Vector((sx * 0.140, 0.10, 1.650))]
        for z in np.linspace(1.58, 1.10, 8):
            x = sx * (0.080 + 0.05 * (z - 1.10) / 0.48)
            i = int(round((x - body_F.lo[0]) / body_F.h)); kk = int(round((z - body_F.lo[2]) / body_F.h))
            col = body_F.D[i, :, kk]; inside = np.where(col <= 0)[0]
            yb = body_F.lo[1] + body_F.h * inside[-1] if len(inside) else 0.15
            path.append(Vector((x, yb + 0.004, z)))
        for a, b in zip(path, path[1:]):
            for off in (-0.009, 0.0, 0.009):
                o = Vector((off, 0, 0))
                S.cap(a + o, b + o, 0.0055, k=0.006)
        S.ell(path[0] + Vector((0, -0.006, 0.01)), (0.020, 0.008, 0.020), k=0.004)          # button
    sus = B.field_object(S, "Suspenders", coll, iters=2); sus.data.materials.append(mats["strap"]); out.append(sus)

    R = Field((-0.27, -0.27, 1.50), (0.27, 0.27, 1.72), h * 0.75)
    B.torus_frill(R, (0, 0.010, 1.600), (0, -0.2, 1), 0.150, 0.030, 28, 0.020)
    B.torus_frill(R, (0, 0.010, 1.628), (0, -0.2, 1), 0.118, 0.024, 24, 0.016)
    ruff = B.field_object(R, "Ruff", coll, iters=1); ruff.data.materials.append(mats["ruff"]); out.append(ruff)
    for sx in (1, -1):
        s, e, w, d = A.arm_points(sx)
        c = w - d * 0.02
        Rf = Field(tuple(c - Vector((0.13,) * 3)), tuple(c + Vector((0.13,) * 3)), h * 0.75)
        B.torus_frill(Rf, c, d, 0.064, 0.018, 18, 0.012)
        f = B.field_object(Rf, f"Cuff_{'LR'[sx < 0]}", coll, iters=1); f.data.materials.append(mats["ruff"]); out.append(f)
    for sx in (1, -1):
        an = Vector((A.ANKLE[0] * sx, A.ANKLE[1], A.ANKLE[2]))
        Sh = Field((an.x - 0.16, -0.48, -0.01), (an.x + 0.16, 0.14, 0.24), h)
        Sh.ell(an + Vector((0, -0.08, -0.040)), (0.085, 0.17, 0.065), k=0.04)
        Sh.ell(an + Vector((sx * 0.008, -0.26, -0.030)), (0.098, 0.098, 0.074), k=0.06)
        Sh.cap(an + Vector((0, 0.01, -0.02)), an + Vector((0, 0.01, 0.08)), 0.075, 0.068, k=0.04)
        Sh.shape(B.halfspace((0, 0, 0.004), (0, 0, -1)), (an.x - 0.3, -0.6, -0.05), (an.x + 0.3, 0.3, 0.02), k=0.004, neg=True)
        sh = B.field_object(Sh, f"Shoe_{'LR'[sx < 0]}", coll); sh.data.materials.append(mats["shoe"]); out.append(sh)
    return out


def materials():
    return {
        "skin": B.mat_skin(), "eye": mat_eye_brute(), "nose": B.mat_nose(),
        "teeth": B.mat_simple("Teeth", (0.62, 0.52, 0.34), 0.28, **{"Subsurface Weight": 0.15, "Coat Weight": 0.3}),
        "gums": B.mat_simple("Gums", (0.30, 0.04, 0.05), 0.25, **{"Subsurface Weight": 0.3}),
        "nails": B.mat_simple("Nails", (0.20, 0.17, 0.10), 0.35, **{"Coat Weight": 0.4}),
        "hair": B.mat_simple("Hair", (0.36, 0.055, 0.02), 0.55, **{"Sheen Weight": 0.6}),
        "pants": B.mat_cloth("Pants_Stripes", (0.40, 0.04, 0.035), (0.55, 0.50, 0.38), 7.0),
        "strap": B.mat_simple("Strap_Leather", (0.10, 0.035, 0.02), 0.62),
        "ruff": B.mat_cloth("Ruff_Linen", (0.68, 0.64, 0.54), (0.60, 0.56, 0.46), 3.0, 0.9),
        "shoe": B.mat_simple("Shoe_Leather", (0.17, 0.02, 0.02), 0.35, **{"Coat Weight": 0.35}),
    }


def mat_eye_brute():
    m = B.mat_eye()
    nt = m.node_tree; b = [n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED'][0]
    b.inputs["Emission Color"].default_value = (1.0, 0.75, 0.15, 1)
    b.inputs["Emission Strength"].default_value = 0.35
    return m


def build_high():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    mats = materials()
    anat = B.new_coll("Body"); face = B.new_coll("Face"); cost = B.new_coll("Costume")
    F = A.body_field(h=0.0040 if QUICK else 0.0021)
    body = B.field_object(F, "Clown_Body", anat, iters=2)
    paint(body); body.data.materials.append(mats["skin"])
    face_parts(face, mats); teeth(face, mats); hair(face, mats)
    costume(cost, mats, F)
    return mats


if __name__ == "__main__":
    build_high()
    if MODE == "preview":
        sys.argv = ["render.py", sys.argv[2], "--quick"] + sys.argv[3:]
        import render as R
        R.OUT = sys.argv[1]; os.makedirs(R.OUT, exist_ok=True)
        R.stage(); R.clay_mat()
        k = 0.5
        for s in sys.argv[3:] or ["hero", "face"]:
            if s == "hero":
                R.studio(False); R.show_costume(True); R.shoot(s, (600, 800), ((1.1, -3.4, 1.35), (0, 0, 1.05), 40))
            elif s == "face":
                R.studio(False); R.show_costume(True); R.shoot(s, (700, 700), ((0.22, -0.78, 1.80), (0, -0.05, 1.77), 75))
            elif s == "clay":
                R.studio(True); R.show_costume(False, clay=True); R.shoot(s, (500, 800), ((0, -4.6, 1.0), (0, 0, 0.98), 50))
            elif s == "clayface":
                R.studio(True); R.show_costume(False, clay=True); R.shoot(s, (700, 700), ((0.25, -0.75, 1.80), (0, -0.05, 1.77), 75))


# ================================================================== game LOD
LOD = {  # name: (quad faces target or None to keep, texture size)
    "Clown_Body": (13000, 2048), "Pants": (2600, 1024), "Ruff": (2200, 1024), "Hair": (1800, 512),
    "Suspenders": (700, 512), "Cuff_L": (500, 256), "Cuff_R": (500, 256), "Shoe_L": (1100, 512), "Shoe_R": (1100, 512),
    "Teeth": (None, 512), "Gums": (None, 256), "Eye_L": (None, 256), "Eye_R": (None, 256), "Nose": (None, 512),
    "Nails": (None, 256),
}


def tris(o):
    return sum(len(p.vertices) - 2 for p in o.data.polygons)


def only(objs, active=None):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = active or objs[0]


def to_mesh_copy(hi, name):
    deps = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(hi.evaluated_get(deps))
    lo = bpy.data.objects.new(name, me); lo.matrix_world = hi.matrix_world
    return lo


def make_lod(hi, faces, coll):
    lo = to_mesh_copy(hi, hi.name + "_LOD0"); coll.objects.link(lo)
    if faces:
        only([lo])
        if len(lo.data.polygons) > 250000:
            d = lo.modifiers.new("pre", 'DECIMATE'); d.ratio = 250000 / len(lo.data.polygons)
            bpy.ops.object.modifier_apply(modifier="pre")
        bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.normals_make_consistent(inside=False); bpy.ops.object.mode_set(mode='OBJECT')
        r = bpy.ops.object.quadriflow_remesh(target_faces=faces, seed=1)
        if 'FINISHED' not in r:
            print("quadriflow failed for", hi.name, "- decimating instead")
            d = lo.modifiers.new("dec", 'DECIMATE'); d.ratio = faces * 2 / max(1, tris(lo))
            bpy.ops.object.modifier_apply(modifier="dec")
    lo.data.materials.clear()
    for p in lo.data.polygons:
        p.use_smooth = True
    only([lo])
    bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=0.004)
    bpy.ops.object.mode_set(mode='OBJECT')
    return lo


def bake_maps(hi, lo, size, out_dir):
    sc = bpy.context.scene
    base = lo.name.replace("_LOD0", "")
    ic = bpy.data.images.new(base + "_BaseColor", size, size)
    inn = bpy.data.images.new(base + "_Normal", size, size); inn.colorspace_settings.name = 'Non-Color'
    m, nt, b = B.nodes_mat(base + "_Game")
    tc = nt.nodes.new("ShaderNodeTexImage"); tc.image = ic
    tn = nt.nodes.new("ShaderNodeTexImage"); tn.image = inn
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nt.links.new(tc.outputs[0], b.inputs["Base Color"])
    nt.links.new(tn.outputs[0], nm.inputs["Color"]); nt.links.new(nm.outputs[0], b.inputs["Normal"])
    src = hi.active_material.node_tree.nodes
    hb = [n for n in src if n.type == 'BSDF_PRINCIPLED']
    if hb:
        for k in ("Roughness", "Coat Weight", "Subsurface Weight", "Sheen Weight", "Emission Strength"):
            if not hb[0].inputs[k].is_linked:
                b.inputs[k].default_value = hb[0].inputs[k].default_value
        b.inputs["Emission Color"].default_value = hb[0].inputs["Emission Color"].default_value
        if hb[0].inputs["Roughness"].is_linked:
            b.inputs["Roughness"].default_value = 0.5
    lo.data.materials.append(m)
    hide = hi.hide_render; hi.hide_render = False
    only([hi, lo], active=lo)
    bk = sc.render.bake
    bk.use_selected_to_active = True; bk.cage_extrusion = 0.010; bk.max_ray_distance = 0.03; bk.margin = 6
    for img, kind, node in ((ic, 'DIFFUSE', tc), (inn, 'NORMAL', tn)):
        nt.nodes.active = node
        bk.use_pass_direct = False; bk.use_pass_indirect = False; bk.use_pass_color = True
        bpy.ops.object.bake(type=kind)
        img.filepath_raw = os.path.join(out_dir, img.name + ".png"); img.file_format = 'PNG'; img.save()
    hi.hide_render = hide


BONES = []


def skeleton(coll):
    arm = bpy.data.armatures.new("Clown_Rig"); rig = bpy.data.objects.new("Clown_Rig", arm); coll.objects.link(rig)
    only([rig]); bpy.ops.object.mode_set(mode='EDIT')

    def bone(name, h, t, parent=None):
        b = arm.edit_bones.new(name); b.head = Vector(h); b.tail = Vector(t)
        if parent:
            b.parent = arm.edit_bones[parent]; b.use_connect = (b.parent.tail - b.head).length < 1e-4
        BONES.append(name); return name
    bone("Hips", (0, 0.02, 0.98), (0, 0.02, 1.12))
    bone("Spine", (0, 0.02, 1.12), (0, 0.02, 1.28), "Hips")
    bone("Spine1", (0, 0.02, 1.28), (0, 0.02, 1.45), "Spine")
    bone("Spine2", (0, 0.02, 1.45), (0, 0.02, 1.60), "Spine1")
    bone("Neck", (0, 0.02, 1.60), (0, 0.01, 1.70), "Spine2")
    bone("Head", (0, 0.01, 1.70), (0, 0.01, 1.96), "Neck")
    bone("Jaw", (0, -0.01, 1.735), (0, -0.095, 1.668), "Head")
    for sx, side in ((1, "Left"), (-1, "Right")):
        s, e, w, d = A.arm_points(sx)
        bone(side + "Shoulder", (sx * 0.06, 0.02, 1.575), s, "Spine2")
        bone(side + "Arm", s, e, side + "Shoulder")
        bone(side + "ForeArm", e, w, side + "Arm")
        bone(side + "Hand", w, w + d * 0.105, side + "ForeArm")
        for fi, fname in enumerate(("Thumb", "Index", "Middle", "Ring", "Pinky")):
            J = A.JOINTS[(sx, fi)]; par = side + "Hand"
            for k in range(3):
                par = bone(f"{side}Hand{fname}{k + 1}", J[k], J[k + 1], par)
        h = Vector((A.HIP[0] * sx, A.HIP[1], A.HIP[2])); kn = Vector((A.KNEE[0] * sx, A.KNEE[1], A.KNEE[2]))
        an = Vector((A.ANKLE[0] * sx, A.ANKLE[1], A.ANKLE[2]))
        bone(side + "UpLeg", h, kn, "Hips")
        bone(side + "Leg", kn, an, side + "UpLeg")
        bone(side + "Foot", an, an + Vector((0, -0.13, -0.075)), side + "Leg")
        bone(side + "ToeBase", an + Vector((0, -0.13, -0.075)), an + Vector((0, -0.34, -0.075)), side + "Foot")
    bpy.ops.object.mode_set(mode='OBJECT')
    return rig


def skin(rig, body, others):
    only([body, rig], active=rig)
    bpy.ops.object.parent_set(type='ARMATURE_AUTO')
    rigid = {"Eye_L", "Eye_R", "Nose", "Teeth", "Gums", "Hair"}
    for o in others:
        base = o.name.replace("_LOD0", "")
        if base in rigid:
            vg = o.vertex_groups.new(name="Head"); vg.add(list(range(len(o.data.vertices))), 1.0, 'REPLACE')
        else:                                   # clothes inherit the body's weights (nearest surface)
            for g in body.vertex_groups:
                o.vertex_groups.new(name=g.name)
            dt = o.modifiers.new("weights", 'DATA_TRANSFER'); dt.object = body
            dt.use_vert_data = True; dt.data_types_verts = {'VGROUP_WEIGHTS'}
            dt.vert_mapping = 'POLYINTERP_NEAREST'
            only([o]); bpy.ops.object.datalayout_transfer(modifier="weights")
            bpy.ops.object.modifier_apply(modifier="weights")
        o.parent = rig
        mod = o.modifiers.new("Armature", 'ARMATURE'); mod.object = rig


def pose_menace(rig):
    """Hunched, head down, arms reaching forward: a stalking pose for the hero shot."""
    import mathutils
    only([rig]); bpy.ops.object.mode_set(mode='POSE')
    pb = rig.pose.bones

    def turn(name, axis, deg):
        b = pb[name]; bpy.context.view_layer.update()
        h = b.head.copy()
        R = mathutils.Matrix.Rotation(math.radians(deg), 4, axis)
        b.matrix = mathutils.Matrix.Translation(h) @ R @ mathutils.Matrix.Translation(-h) @ b.matrix
        bpy.context.view_layer.update()
    turn("Spine1", 'X', 9); turn("Spine2", 'X', 6); turn("Neck", 'X', 8); turn("Head", 'X', 10)
    turn("Head", 'Y', -6); turn("Jaw", 'X', -6)
    for side, sx in (("Left", 1), ("Right", -1)):
        turn(side + "Arm", 'X', 34); turn(side + "Arm", 'Y', sx * 14)
        turn(side + "ForeArm", 'X', 32)
        for f in ("Index", "Middle", "Ring", "Pinky"):
            for k in (1, 2, 3):
                b = pb[f"{side}Hand{f}{k}"]
                bpy.context.view_layer.update()
                axis = (b.matrix.to_3x3() @ Vector((1, 0, 0))).normalized()
                R = mathutils.Matrix.Rotation(math.radians(18), 4, axis)
                h = b.head.copy()
                b.matrix = mathutils.Matrix.Translation(h) @ R @ mathutils.Matrix.Translation(-h) @ b.matrix
        turn(side + "UpLeg", 'X', -6); turn(side + "Leg", 'X', 10)
    bpy.ops.object.mode_set(mode='OBJECT')


def wire_mat():
    m, nt, b = B.nodes_mat("Topology")
    b.inputs["Base Color"].default_value = (0.62, 0.60, 0.58, 1); b.inputs["Roughness"].default_value = 0.55
    out = [n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL'][0]
    wf = nt.nodes.new("ShaderNodeWireframe"); wf.use_pixel_size = True; wf.inputs[0].default_value = 0.9
    em = nt.nodes.new("ShaderNodeBsdfDiffuse"); em.inputs[0].default_value = (0.02, 0.05, 0.10, 1)
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(wf.outputs[0], mix.inputs[0]); nt.links.new(b.outputs[0], mix.inputs[1]); nt.links.new(em.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs[0])
    return m


def full():
    out_dir = os.path.join(HERE, "brute"); tex_dir = os.path.join(out_dir, "textures"); ren = os.path.join(out_dir, "renders")
    for d in (tex_dir, ren):
        os.makedirs(d, exist_ok=True)
    build_high()
    sc = bpy.context.scene; sc.render.engine = 'CYCLES'; sc.cycles.samples = 1; sc.cycles.device = 'CPU'
    for c in ("Body", "Face", "Costume"):
        bpy.data.collections[c].name = c + "_HighPoly"
    for o in list(bpy.data.objects):
        if o.type == 'CURVE':
            only([o]); bpy.ops.object.convert(target='MESH')
    game = B.new_coll("Game_LOD0")
    lows = {}
    for name, (faces, size) in LOD.items():
        hi = bpy.data.objects[name]
        lo = make_lod(hi, faces, game)
        bake_maps(hi, lo, size, tex_dir)
        lows[name] = lo
        print(f"LOD {name}: {tris(hi)} -> {tris(lo)} tris", flush=True)
    rig = skeleton(game)
    skin(rig, lows["Clown_Body"], [o for n, o in lows.items() if n != "Clown_Body"])
    total = sum(tris(o) for o in lows.values())
    print("TOTAL TRIS", total, "BONES", len(BONES), flush=True)
    only(list(lows.values()) + [rig], active=rig)
    bpy.ops.export_scene.gltf(filepath=os.path.join(out_dir, "clown_brute.glb"), use_selection=True,
                              export_format='GLB', export_skins=True, export_animations=False)
    bpy.ops.export_scene.fbx(filepath=os.path.join(out_dir, "clown_brute.fbx"), use_selection=True,
                             add_leaf_bones=False, path_mode='COPY', embed_textures=True)
    for c in ("Body", "Face", "Costume"):
        bpy.data.collections[c + "_HighPoly"].hide_render = True
        bpy.data.collections[c + "_HighPoly"].hide_viewport = True
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out_dir, "clown_brute.blend"), compress=True)
    return lows, rig, ren, total


if __name__ == "__main__" and MODE == "full":
    lows, rig, ren, total = full()
    sys.argv = ["render.py", ren]
    import render as R
    R.OUT = ren
    R.stage(); B.nodes_mat  # lights + floor
    sc = bpy.context.scene; sc.cycles.samples = 160
    sc.render.film_transparent = False

    def studio(on):
        for o in bpy.data.objects:
            if o.type == 'LIGHT':
                o.hide_render = o.name.startswith("Studio") != on
        bpy.data.objects["Floor"].hide_render = on
        sc.world.node_tree.nodes["Background"].inputs[0].default_value = (0.20, 0.20, 0.21, 1) if on else (0.004, 0.005, 0.006, 1)
    # A-pose: the game asset as delivered
    studio(False); R.shoot("lod0_front", (1100, 1400), ((0.9, -3.5, 1.30), (0, 0, 1.02), 40))
    R.shoot("lod0_face", (1200, 1200), ((0.24, -0.80, 1.80), (0, -0.05, 1.77), 75))
    R.shoot("lod0_back", (1100, 1400), ((-1.6, 3.0, 1.35), (0, 0, 1.02), 40))
    # topology
    wm = wire_mat(); studio(True)
    bpy.context.view_layer.material_override = wm
    R.shoot("topology_full", (900, 1400), ((0, -4.4, 1.0), (0, 0, 0.98), 46))
    R.shoot("topology_face", (1000, 1000), ((0.26, -0.82, 1.80), (0, -0.05, 1.77), 75))
    bpy.context.view_layer.material_override = None
    # high-poly sculpt, clay
    for c in ("Body", "Face"):
        bpy.data.collections[c + "_HighPoly"].hide_render = False
    bpy.data.collections["Game_LOD0"].hide_render = True
    R.clay_mat(); bpy.context.view_layer.material_override = bpy.data.materials["Clay"]
    R.shoot("sculpt_face", (1000, 1000), ((0.26, -0.82, 1.80), (0, -0.05, 1.77), 75))
    R.shoot("sculpt_body", (900, 1400), ((0.5, -4.4, 1.0), (0, 0, 0.98), 46))
    bpy.context.view_layer.material_override = None
    for c in ("Body", "Face"):
        bpy.data.collections[c + "_HighPoly"].hide_render = True
    bpy.data.collections["Game_LOD0"].hide_render = False
    # posed hero
    pose_menace(rig); studio(False)
    R.shoot("hero_pose", (1200, 1500), ((0.75, -2.7, 1.05), (0, -0.1, 1.15), 38))
    R.shoot("hero_pose_face", (1200, 1200), ((0.18, -0.95, 1.55), (0, -0.12, 1.70), 70))
    print("DONE", total)
