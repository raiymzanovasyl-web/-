"""Clown v3: heavy-set body, head from the client's reference sculpt, clothes that fit,
blood, ~200k-triangle game mesh with baked maps and a skeleton.
python clown3.py <reference_mask.fbx> [preview|full]"""
import math, os, random, sys
import numpy as np
import bpy, bmesh
from mathutils import Vector, Quaternion, Matrix
from scipy import ndimage

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
MASK = sys.argv[1]; MODE = sys.argv[2] if len(sys.argv) > 2 else "preview"
sys.argv = [sys.argv[0], "lib"]                      # keep imported modules from reading our args
import build as B
import brute as BR
import fat_anatomy as A
import head as Hd
from sdf import Field, front_y
BR.A = A                                              # the skeleton builder reads joints from here
QUICK = MODE in ("preview", "fullquick")
OUT = os.path.join(HERE, "v3") if MODE != "fullquick" else os.environ.get("V3_TMP", "/tmp/v3q")
rng = np.random.default_rng(12)


# ================================================================== blood in materials
def add_blood(m, wet=0.12, color=(0.16, 0.004, 0.007)):
    nt = m.node_tree
    b = [n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED'][0]
    at = nt.nodes.new("ShaderNodeVertexColor"); at.layer_name = "blood"
    sep = nt.nodes.new("ShaderNodeSeparateColor"); nt.links.new(at.outputs["Color"], sep.inputs[0])
    fac = sep.outputs[0]
    mc = nt.nodes.new("ShaderNodeMix"); mc.data_type = 'RGBA'
    nt.links.new(fac, mc.inputs["Factor"]); mc.inputs[7].default_value = (*color, 1)
    bc = b.inputs["Base Color"]
    if bc.is_linked:
        nt.links.new(bc.links[0].from_socket, mc.inputs[6])
    else:
        mc.inputs[6].default_value = bc.default_value
    nt.links.new(mc.outputs[2], bc)
    mr = nt.nodes.new("ShaderNodeMix"); mr.data_type = 'FLOAT'
    nt.links.new(fac, mr.inputs["Factor"]); mr.inputs[3].default_value = wet
    r = b.inputs["Roughness"]
    if r.is_linked:
        nt.links.new(r.links[0].from_socket, mr.inputs[2])
    else:
        mr.inputs[2].default_value = r.default_value
    nt.links.new(mr.outputs[0], r)
    return m


def set_attr(o, name, values):
    a = o.data.color_attributes.new(name, 'FLOAT_COLOR', 'POINT')
    a.data.foreach_set("color", np.repeat(np.clip(values, 0, 1)[:, None], 4, 1).astype(np.float32).ravel())


def verts(o):
    co = np.empty(len(o.data.vertices) * 3, np.float32); o.data.vertices.foreach_get("co", co)
    return co.reshape(-1, 3)


def streaks(co, starts, front_mask, wob=0.004):
    """Drips running down: each start (x, z_top, length, width)."""
    x, z = co[:, 0], co[:, 2]
    out = np.zeros(len(co))
    for sx, top, L, w in starts:
        wav = wob * np.sin((top - z) * 60 + sx * 40)
        width = w * (0.7 + 0.3 * np.clip((top - z) / L, 0, 1))
        s = np.clip(1 - np.abs(x - sx - wav) / width, 0, 1) * (z < top) * (z > top - L)
        tip = np.clip(1 - np.hypot(x - sx - wob * np.sin(L * 60 + sx * 40), (z - (top - L)) * 1.2) / (w * 1.5), 0, 1)
        out = np.maximum(out, np.maximum(s, tip))
    return out * front_mask


def spatter(co, centre, spread, count, rmin, rmax, front_mask):
    out = np.zeros(len(co))
    for _ in range(count):
        c = np.array(centre) + rng.normal(0, 1, 3) * np.array(spread)
        r = rng.uniform(rmin, rmax)
        out = np.maximum(out, np.clip((r - np.linalg.norm(co - c, axis=1)) / (r * 0.35), 0, 1))
    return out * front_mask


# ================================================================== body + head
def paint_body(o):
    BR.paint(o) if False else None
    co = verts(o); n = len(co)
    x, y, z = co.T
    skin = np.array([0.55, 0.47, 0.42])
    noise = 0.9 + 0.1 * np.sin(x * 80) * np.sin(y * 70 + z * 50)
    col = skin[None, :] * noise[:, None]
    a = o.data.color_attributes.new("makeup", 'FLOAT_COLOR', 'POINT')
    a.data.foreach_set("color", np.concatenate([col, np.zeros((n, 1))], 1).astype(np.float32).ravel())
    blood = np.zeros(n)
    for p, d, inward, _ in A.NAILS:                                           # bloody hands
        dd = np.linalg.norm(co - np.array(p), axis=1)
        blood = np.maximum(blood, np.clip((0.085 - dd) / 0.03, 0, 1) * (0.65 + 0.35 * np.sin(co[:, 0] * 300) ** 2))
    for sx in (1, -1):                                                        # running down the forearms
        s, e, w, d = A.arm_points(sx)
        t = (co - np.array(w)) @ np.array(-d)
        rad = np.linalg.norm((co - np.array(w)) - np.outer(t, -np.array(d)), axis=1)
        band = (t > 0) & (t < 0.16) & (rad < 0.06)
        blood = np.maximum(blood, band * np.clip(np.sin(np.arctan2(co[:, 1] - w.y, co[:, 0] - w.x) * 7) * 2 - 0.6, 0, 1)
                           * np.clip(1 - t / 0.16, 0, 1))
    set_attr(o, "blood", blood)


def build_body(coll, mats):
    F = A.body_field(h=0.0040 if QUICK else 0.0021)
    o = B.field_object(F, "Body", coll, iters=3)
    paint_body(o); o.data.materials.append(mats["skin"])
    # the head takes over above the collar line
    bm = bmesh.new(); bm.from_mesh(o.data)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.z > 1.605], context='VERTS')
    bm.to_mesh(o.data); bm.free()
    return o, F


def build_head(coll, mats):
    F = Hd.head_field(MASK, h=0.0016 if QUICK else 0.0009)
    o = B.field_object(F, "Head", coll, iters=1)
    bm = bmesh.new(); bm.from_mesh(o.data)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.z < 1.575], context='VERTS')
    bm.to_mesh(o.data); bm.free()
    Hd.paint_head(o)
    o.data.materials.append(mats["skin"])
    eyes = []
    for i, (c, r) in enumerate(Hd.INFO["eyes"]):
        bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, radius=r, location=c)
        e = bpy.context.object; e.name = f"Eye_{'LR'[c.x < 0]}"; B.link(e, coll)
        bpy.ops.object.shade_smooth(); e.data.materials.append(mats["eye"]); eyes.append(e)
    return o, eyes


# ================================================================== clothes from the body
def crop(F, lo, hi):
    i0 = np.clip(((np.array(lo) - F.lo) / F.h).astype(int), 0, F.n - 1)
    i1 = np.clip(((np.array(hi) - F.lo) / F.h).astype(int) + 1, 1, F.n)
    G = Field(tuple(F.lo + i0 * F.h), tuple(F.lo + (i1 - 1) * F.h), F.h)
    G.n = i1 - i0; G.D = F.D[i0[0]:i1[0], i0[1]:i1[1], i0[2]:i1[2]].copy()
    return G


def grid(G):
    return [(G.lo[k] + G.h * np.arange(G.n[k], dtype=np.float32)).reshape([-1 if j == k else 1 for j in range(3)]) for k in range(3)]


def cloth_from_body(F, lo, hi, blur, offset):
    G = crop(F, lo, hi)
    G.D = (ndimage.gaussian_filter(G.D, blur / G.h) - offset).astype(np.float32)
    return G


def arm_axis_terms(X, Y, Z, sx):
    s, e, w, d = A.arm_points(sx)
    P = (X - s.x, Y - s.y, Z - s.z)
    t = P[0] * d.x + P[1] * d.y + P[2] * d.z
    return t, s, e, w, d


def build_shirt(F, coll, mats):
    h = F.h
    S = cloth_from_body(F, (-0.75, -0.40, 0.95), (0.75, 0.32, 1.68), 0.010, 0.013)
    X, Y, Z = grid(S)
    # cut: neck hole, wrists, hem tucked into the trousers
    S.D = np.maximum(S.D, 0.105 - np.sqrt(X ** 2 + (Y - 0.015) ** 2) - np.clip((1.585 - Z) * 4, 0, None))
    S.D = np.maximum(S.D, Z - 1.66)
    S.D = np.maximum(S.D, 0.985 - Z)
    for sx in (1, -1):
        t, s, e, w, d = arm_axis_terms(X, Y, Z, sx)
        side = (X * sx > 0.18)
        S.D = np.where(side, np.maximum(S.D, t - (A.UPPER + A.FORE - 0.035)), S.D)
        # sleeve folds: bunching inside the elbow and at the cuff
        el = np.exp(-((t - A.UPPER) / 0.05) ** 2); cf = np.exp(-((t - (A.UPPER + A.FORE - 0.06)) / 0.04) ** 2)
        ang = np.arctan2(Z - (s.z + d.z * t), Y - (s.y + d.y * t))
        ph = 2.5 * np.sin(ang * 2 + 1.3) + 1.5 * np.sin(ang * 3 - t * 30)
        S.D = np.where(side & (np.abs(S.D) < 0.02),
                       S.D - 0.0030 * np.sin(t * 150 + ph) * (0.6 + 0.4 * np.sin(ang * 5)) * (el + 0.7 * cf), S.D)
    # strain folds across the belly, drape from the chest, soft wrinkles everywhere
    belly = np.exp(-((Z - 1.12) / 0.10) ** 2) * (Y < -0.05)
    chest = np.exp(-((Z - 1.42) / 0.10) ** 2) * (np.abs(X) < 0.25)
    S.D = np.where(np.abs(S.D) < 0.02, S.D - (0.0022 * np.sin(Z * 80 + 9 * np.sin(X * 11) + 3 * np.sin(X * 31)) * belly
                                               * (0.5 + 0.5 * np.sin(X * 23 + 1.0))
                                               + 0.0008 * np.sin(X * 150 + Y * 90 + Z * 120)), S.D).astype(np.float32)
    S.shell(0.006)
    o = B.field_object(S, "Shirt", coll, iters=2); o.data.materials.append(mats["shirt"])
    # placket and buttons down the front, laid on the cloth
    btn = []
    for z in np.linspace(1.08, 1.54, 6):
        yf = front_y(S, 0.0, z, y0=-0.42, y1=0.1)
        if yf is not None:
            btn.append(Vector((0.0, yf - 0.002, z)))
    return o, S, btn


def build_pants(F, coll, mats):
    P = cloth_from_body(F, (-0.40, -0.40, 0.10), (0.40, 0.30, 1.16), 0.016, 0.017)
    X, Y, Z = grid(P)
    T = Field(tuple(P.lo), tuple(P.lo + P.h * (P.n - 1)), P.h); T.n = P.n.copy(); T.D = np.full(tuple(P.n), 0.05, np.float32)
    for sx in (1, -1):                                     # legs hang as tubes from the thigh to the shoe
        hp, kn, an = (Vector((v[0] * sx, v[1], v[2])) for v in (A.HIP, A.KNEE, A.ANKLE))
        T.cap(hp - Vector((0, 0, 0.10)), kn, 0.120, 0.104, k=0.0)
        T.cap(kn, an + Vector((0, -0.01, 0.06)), 0.104, 0.098, k=0.0)
    kk = 0.05
    hh = np.clip(0.5 + 0.5 * (P.D - T.D) / kk, 0, 1)
    P.D = (P.D * (1 - hh) + T.D * hh - kk * hh * (1 - hh)).astype(np.float32)
    # waist sits under the belly at the front, higher at the back; hem breaks on the shoe
    n = np.array([0, -0.27, 0.963]); n /= np.linalg.norm(n)
    P.D = np.maximum(P.D, (X * n[0] + (Y + 0.20) * n[1] + (Z - 1.005) * n[2]))
    P.D = np.maximum(P.D, 0.15 - Z)
    knee = np.exp(-((Z - 0.52) / 0.07) ** 2); ankle = np.exp(-((Z - 0.22) / 0.07) ** 2)
    ang = np.arctan2(Y - 0.02, X - np.sign(X) * 0.14)
    ph = 3.0 * np.sin(ang * 2 + X * 40) + 2.0 * np.sin(ang * 3 - 1.1)
    amp = 0.55 + 0.45 * np.sin(ang * 4 + Z * 20)
    drape = 0.0018 * np.sin(ang * 7 + Z * 9 + 2 * np.sin(Z * 13))
    P.D = np.where(np.abs(P.D) < 0.02, P.D - (0.0026 * np.sin(Z * 120 + ph) * knee * (Y > -0.02) * amp
                                               + 0.0038 * np.sin(Z * 105 + ph) * ankle * amp + drape * (Z < 0.95)), P.D).astype(np.float32)
    P.shell(0.006)
    o = B.field_object(P, "Pants", coll, iters=2); o.data.materials.append(mats["pants"])
    return o, P


def scan_back(G, x, z):
    i = int(round((x - G.lo[0]) / G.h)); k = int(round((z - G.lo[2]) / G.h))
    if not (0 <= i < G.n[0] and 0 <= k < G.n[2]):
        return None
    inside = np.where(G.D[i, :, k] <= 0)[0]
    return float(G.lo[1] + G.h * inside[-1]) if len(inside) else None


def build_suspenders(S, coll, mats):
    G = Field((-0.35, -0.45, 0.95), (0.35, 0.35, 1.75), 0.0025 if not QUICK else 0.004)
    for sx in (1, -1):
        path = []
        for z in np.linspace(1.03, 1.52, 10):
            x = sx * (0.095 + 0.035 * (z - 1.03) / 0.49)
            yf = front_y(S, x, z, y0=-0.45, y1=0.2)
            if yf is not None:
                path.append(Vector((x, yf - 0.003, z)))
        path += [Vector((sx * 0.140, -0.080, 1.600)), Vector((sx * 0.150, 0.020, 1.655)), Vector((sx * 0.135, 0.120, 1.600))]
        for z in np.linspace(1.52, 1.08, 9):
            x = sx * (0.070 + 0.065 * (z - 1.08) / 0.44)
            yb = scan_back(S, x, z)
            if yb is not None:
                path.append(Vector((x, yb + 0.003, z)))
        for a, b in zip(path, path[1:]):
            for off in (-0.010, 0.0, 0.010):
                G.cap(a + Vector((off, 0, 0)), b + Vector((off, 0, 0)), 0.0042, k=0.006)
        G.ell(path[0] + Vector((0, -0.004, 0.0)), (0.022, 0.006, 0.016), k=0.004)          # clip
    o = B.field_object(G, "Suspenders", coll, iters=2); o.data.materials.append(mats["strap"])
    return o


def build_trims(coll, mats, buttons):
    out = []
    R = Field((-0.27, -0.27, 1.48), (0.27, 0.27, 1.72), 0.0024 if not QUICK else 0.004)
    B.torus_frill(R, (0, 0.012, 1.592), (0, -0.16, 1), 0.150, 0.030, 30, 0.020)
    B.torus_frill(R, (0, 0.012, 1.618), (0, -0.16, 1), 0.122, 0.024, 26, 0.016)
    r = B.field_object(R, "Ruff", coll, iters=1); r.data.materials.append(mats["ruff"]); out.append(r)
    for sx in (1, -1):
        s, e, w, d = A.arm_points(sx)
        c = w - d * 0.030
        Rf = Field(tuple(c - Vector((0.12,) * 3)), tuple(c + Vector((0.12,) * 3)), 0.0022 if not QUICK else 0.004)
        B.torus_frill(Rf, c, d, 0.062, 0.016, 18, 0.011)
        f = B.field_object(Rf, f"Cuff_{'LR'[sx < 0]}", coll, iters=1); f.data.materials.append(mats["ruff"]); out.append(f)
    for sx in (1, -1):
        an = Vector((A.ANKLE[0] * sx, A.ANKLE[1], A.ANKLE[2]))
        Sh = Field((an.x - 0.16, -0.48, -0.01), (an.x + 0.16, 0.14, 0.25), 0.0030 if not QUICK else 0.005)
        Sh.ell(an + Vector((0, -0.075, -0.040)), (0.090, 0.165, 0.066), k=0.04)
        Sh.ell(an + Vector((sx * 0.008, -0.250, -0.030)), (0.100, 0.100, 0.075), k=0.06)
        Sh.cap(an + Vector((0, 0.010, -0.020)), an + Vector((0, 0.010, 0.085)), 0.080, 0.072, k=0.04)
        Sh.ell(an + Vector((0, -0.075, -0.088)), (0.100, 0.200, 0.012), k=0.01)               # sole
        Sh.shape(B.halfspace((0, 0, 0.004), (0, 0, -1)), (an.x - 0.3, -0.6, -0.05), (an.x + 0.3, 0.3, 0.02), k=0.003, neg=True)
        sh = B.field_object(Sh, f"Shoe_{'LR'[sx < 0]}", coll); sh.data.materials.append(mats["shoe"]); out.append(sh)
    bm = bmesh.new()
    for p in buttons:
        g = bmesh.ops.create_cone(bm, cap_ends=True, segments=16, radius1=0.011, radius2=0.010, depth=0.005)
        bmesh.ops.rotate(bm, verts=g["verts"], cent=(0, 0, 0), matrix=Matrix.Rotation(math.pi / 2, 3, 'X'))
        bmesh.ops.translate(bm, verts=g["verts"], vec=p)
    me = bpy.data.meshes.new("Buttons"); bm.to_mesh(me); bm.free()
    bo = bpy.data.objects.new("Buttons", me); coll.objects.link(bo); me.materials.append(mats["button"]); out.append(bo)
    return out


def blood_clothes(shirt, pants, ruff):
    co = verts(shirt); front = (co[:, 1] < -0.02).astype(float)
    drips = [(rng.uniform(-0.13, 0.13), 1.60 - abs(rng.normal(0, 0.02)), rng.uniform(0.08, 0.40), rng.uniform(0.004, 0.012)) for _ in range(16)]
    b = streaks(co, drips, front, wob=0.006)
    soak = np.clip(1 - np.hypot(co[:, 0] / 0.11, (co[:, 2] - 1.56) / 0.07), 0, 1) * front
    b = np.maximum(b, np.clip(soak * 2.2, 0, 1))
    b = np.maximum(b, spatter(co, (0.0, -0.2, 1.30), (0.14, 0.02, 0.14), 70, 0.002, 0.009, front))
    for sx in (1, -1):                                   # sleeves wiped with bloody hands
        s, e, w, d = A.arm_points(sx)
        dd = np.linalg.norm(co - np.array(w - d * 0.06), axis=1)
        b = np.maximum(b, np.clip((0.07 - dd) / 0.03, 0, 1) * 0.9)
    set_attr(shirt, "blood", b)
    co = verts(pants); front = (co[:, 1] < 0.0).astype(float)
    b = spatter(co, (0.0, -0.2, 0.75), (0.14, 0.03, 0.22), 60, 0.003, 0.012, front)
    for sx in (1, -1):
        b = np.maximum(b, np.clip(1 - np.hypot((co[:, 0] - sx * 0.15) / 0.06, (co[:, 2] - 0.80) / 0.10), 0, 1) * 0.85 * front)
    set_attr(pants, "blood", b)
    co = verts(ruff)
    set_attr(ruff, "blood", np.clip((0.02 - co[:, 1]) / 0.08, 0, 1) * np.clip((1.62 - co[:, 2]) / 0.03, 0, 1)
             * (0.6 + 0.4 * np.sin(co[:, 0] * 90) ** 2))


def materials():
    mats = BR.materials()
    mats["shirt"] = B.mat_dots("Shirt_Dots", (0.40, 0.29, 0.08), (0.20, 0.02, 0.02))
    mats["button"] = B.mat_simple("Button", (0.08, 0.06, 0.05), 0.3, **{"Coat Weight": 0.6})
    for k in ("skin", "shirt", "pants", "ruff"):
        add_blood(mats[k])
    return mats


def build_high():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    mats = materials()
    cb = B.new_coll("Body"); cc = B.new_coll("Costume")
    body, F = build_body(cb, mats)
    head, eyes = build_head(cb, mats)
    BR.face_parts.__globals__["A"] = A
    nails = [o for o in BR.face_parts(cb, mats) if o.name == "Nails"]
    for o in list(bpy.data.objects):
        if o.name.startswith(("Eye_", "Nose")) and o not in eyes:
            bpy.data.objects.remove(o)
    for i, e in enumerate(eyes):
        e.name = f"Eye_{'LR'[i]}"
    shirt, S, buttons = build_shirt(F, cc, mats)
    pants, P = build_pants(F, cc, mats)
    sus = build_suspenders(S, cc, mats)
    trims = build_trims(cc, mats, buttons)
    blood_clothes(shirt, pants, [t for t in trims if t.name == "Ruff"][0])
    return mats


# ================================================================== game mesh
LOD = {  # name: (triangle budget, texture size)
    "Head": (70000, 2048), "Body": (42000, 2048), "Shirt": (26000, 2048), "Pants": (22000, 2048),
    "Ruff": (12000, 1024), "Cuff_L": (2200, 512), "Cuff_R": (2200, 512), "Shoe_L": (4500, 1024), "Shoe_R": (4500, 1024),
    "Suspenders": (3000, 512), "Buttons": (None, 256), "Eye_L": (None, 256), "Eye_R": (None, 256), "Nails": (None, 256),
}


def make_lod(hi, budget, coll):
    lo = BR.to_mesh_copy(hi, hi.name + "_LOD0"); coll.objects.link(lo)
    for a in list(lo.data.color_attributes):
        lo.data.color_attributes.remove(a)
    if budget and BR.tris(lo) > budget:
        BR.only([lo])
        d = lo.modifiers.new("dec", 'DECIMATE'); d.ratio = budget / BR.tris(lo); d.use_collapse_triangulate = True
        bpy.ops.object.modifier_apply(modifier="dec")
    lo.data.materials.clear(); B.outward_normals(lo)
    for p in lo.data.polygons:
        p.use_smooth = True
    BR.only([lo]); bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=0.003)
    bpy.ops.uv.select_all(action='SELECT'); bpy.ops.uv.pack_islands(margin=0.003, rotate=True, scale=True)
    bpy.ops.object.mode_set(mode='OBJECT')
    return lo


def bake(hi, lo, size, tex_dir):
    sc = bpy.context.scene
    base = lo.name.replace("_LOD0", "")
    imgs = {k: bpy.data.images.new(f"{base}_{k}", size, size) for k in ("BaseColor", "Normal", "Roughness")}
    imgs["Normal"].colorspace_settings.name = 'Non-Color'; imgs["Roughness"].colorspace_settings.name = 'Non-Color'
    m, nt, b = B.nodes_mat(base + "_Game")
    nodes = {k: nt.nodes.new("ShaderNodeTexImage") for k in imgs}
    for k, n in nodes.items():
        n.image = imgs[k]
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nt.links.new(nodes["BaseColor"].outputs[0], b.inputs["Base Color"])
    nt.links.new(nodes["Roughness"].outputs[0], b.inputs["Roughness"])
    nt.links.new(nodes["Normal"].outputs[0], nm.inputs["Color"]); nt.links.new(nm.outputs[0], b.inputs["Normal"])
    hb = [n for n in hi.active_material.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'][0]
    for k in ("Coat Weight", "Subsurface Weight", "Sheen Weight", "Emission Strength"):
        if not hb.inputs[k].is_linked:
            b.inputs[k].default_value = hb.inputs[k].default_value
    b.inputs["Emission Color"].default_value = hb.inputs["Emission Color"].default_value
    b.inputs["Subsurface Radius"].default_value = hb.inputs["Subsurface Radius"].default_value
    b.inputs["Subsurface Scale"].default_value = hb.inputs["Subsurface Scale"].default_value
    lo.data.materials.append(m)
    BR.only([hi, lo], active=lo)
    bk = sc.render.bake
    bk.use_selected_to_active = True; bk.cage_extrusion = 0.008; bk.max_ray_distance = 0.02; bk.margin = 6
    bk.use_pass_direct = False; bk.use_pass_indirect = False; bk.use_pass_color = True
    for k, kind in (("BaseColor", 'DIFFUSE'), ("Normal", 'NORMAL'), ("Roughness", 'ROUGHNESS')):
        nt.nodes.active = nodes[k]
        bpy.ops.object.bake(type=kind)
        imgs[k].filepath_raw = os.path.join(tex_dir, imgs[k].name + ".png"); imgs[k].file_format = 'PNG'; imgs[k].save()


def pose_stalk(rig):
    """Head lowered, shoulders rolled, bloody hands half-raised with clawed fingers."""
    BR.only([rig]); bpy.ops.object.mode_set(mode='POSE')
    pb = rig.pose.bones

    def turn(name, axis, deg, local=False):
        b = pb[name]; bpy.context.view_layer.update()
        ax = (b.matrix.to_3x3() @ Vector((1, 0, 0))).normalized() if local else Vector({'X': (1, 0, 0), 'Y': (0, 1, 0), 'Z': (0, 0, 1)}[axis])
        h = b.head.copy()
        b.matrix = Matrix.Translation(h) @ Matrix.Rotation(math.radians(deg), 4, ax) @ Matrix.Translation(-h) @ b.matrix
        bpy.context.view_layer.update()
    turn("Spine1", 'X', 7); turn("Spine2", 'X', 5); turn("Neck", 'X', 6); turn("Head", 'X', 12); turn("Head", 'Z', -8)
    for side, sx in (("Left", 1), ("Right", -1)):
        turn(side + "Arm", 'X', 40); turn(side + "Arm", 'Y', sx * 14)
        turn(side + "ForeArm", 'X', 30); turn(side + "Hand", 'X', -15)
        for f in ("Index", "Middle", "Ring", "Pinky"):
            for k in (1, 2, 3):
                turn(f"{side}Hand{f}{k}", 'X', 20, local=True)
        turn(side + "UpLeg", 'X', -5); turn(side + "Leg", 'X', 9)
    bpy.ops.object.mode_set(mode='OBJECT')


def full():
    tex = os.path.join(OUT, "textures"); os.makedirs(tex, exist_ok=True)
    build_high()
    sc = bpy.context.scene; sc.render.engine = 'CYCLES'; sc.cycles.samples = 1; sc.cycles.device = 'CPU'
    for c in ("Body", "Costume"):
        bpy.data.collections[c].name = c + "_HighPoly"
    game = B.new_coll("Game_LOD0"); lows = {}
    for name, (budget, size) in LOD.items():
        hi = bpy.data.objects[name]
        lo = make_lod(hi, budget, game)
        bake(hi, lo, size, tex)
        lows[name] = lo
        print(f"LOD {name}: {BR.tris(hi)} -> {BR.tris(lo)} tris", flush=True)
    # head and body become one skinned mesh with two materials
    BR.only([lows["Head"], lows["Body"]], active=lows["Body"]); bpy.ops.object.join()
    body = lows.pop("Body"); lows.pop("Head"); body.name = "Clown_Body_LOD0"
    rig = BR.skeleton(game)
    BR.only([body, rig], active=rig); bpy.ops.object.parent_set(type='ARMATURE_AUTO')
    for n, o in lows.items():
        if n.startswith("Eye"):
            vg = o.vertex_groups.new(name="Head"); vg.add(list(range(len(o.data.vertices))), 1.0, 'REPLACE')
        else:
            for g in body.vertex_groups:
                o.vertex_groups.new(name=g.name)
            dt = o.modifiers.new("w", 'DATA_TRANSFER'); dt.object = body
            dt.use_vert_data = True; dt.data_types_verts = {'VGROUP_WEIGHTS'}; dt.vert_mapping = 'POLYINTERP_NEAREST'
            BR.only([o]); bpy.ops.object.datalayout_transfer(modifier="w"); bpy.ops.object.modifier_apply(modifier="w")
        o.parent = rig; o.modifiers.new("Armature", 'ARMATURE').object = rig
    allm = [body] + list(lows.values())
    total = sum(BR.tris(o) for o in allm)
    print("TOTAL TRIS", total, "BONES", len(BR.BONES), flush=True)
    BR.only(allm + [rig], active=rig)
    bpy.ops.export_scene.gltf(filepath=os.path.join(OUT, "clown_v3.glb"), use_selection=True, export_format='GLB',
                              export_skins=True, export_animations=False)
    bpy.ops.export_scene.fbx(filepath=os.path.join(OUT, "clown_v3.fbx"), use_selection=True, add_leaf_bones=False,
                             path_mode='COPY', embed_textures=True)
    for c in ("Body", "Costume"):
        bpy.data.collections[c + "_HighPoly"].hide_render = True
        bpy.data.collections[c + "_HighPoly"].hide_viewport = True
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "clown_v3.blend"), compress=True)
    # a posed copy for the hero shots
    pose_stalk(rig)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "clown_v3_posed.blend"), compress=True, copy=True)
    return total


if __name__ == "__main__" and MODE in ("full", "fullquick"):
    os.makedirs(OUT, exist_ok=True)
    print("DONE", full())

if __name__ == "__main__" and MODE == "preview":
    os.makedirs(OUT, exist_ok=True)
    build_high()
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "preview_high.blend" if QUICK else "clown_v3_high.blend"), compress=True)
    for o in bpy.data.objects:
        if o.type == 'MESH':
            print("MESH", o.name, sum(len(p.vertices) - 2 for p in o.data.polygons))
