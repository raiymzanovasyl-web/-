"""Builds the clown scene: anatomy, face parts, costume, materials, lights.
Run:  python build.py [--quick]   (needs the `bpy` module)"""
import math, random, sys, os
import numpy as np
import bpy
from mathutils import Vector, Quaternion, Matrix, noise

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import anatomy as A
from sdf import Field, front_y, _rot
from meshing import mesh_object

QUICK = "--quick" in sys.argv
random.seed(7)


# ================================================================== utilities
def link(o, coll):
    for c in o.users_collection:
        c.objects.unlink(o)
    coll.objects.link(o)
    return o


def new_coll(name):
    c = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(c)
    return c


def smooth(o, iters=4, factor=0.4):
    m = o.modifiers.new("smooth", 'SMOOTH'); m.factor = factor; m.iterations = iters
    return m


def field_object(F, name, coll, iters=3):
    v, f = F.mesh()
    o = mesh_object(name, v, f)
    smooth(o, iters)
    return link(o, coll)


def torus_frill(F, c, axis, R, r, pleats, amp, flat=1.6, k=0.006):
    """Pleated ruff: a torus around `axis` whose radius ripples `pleats` times."""
    c = np.array(c, np.float32)
    q = Vector((0, 0, 1)).rotation_difference(Vector(axis).normalized())
    M = np.array(q.to_matrix(), np.float32)
    m = R + amp + r * flat + 0.01

    def fn(x, y, z):
        px, py, pz = x - c[0], y - c[1], z - c[2]
        lx = M[0, 0] * px + M[1, 0] * py + M[2, 0] * pz
        ly = M[0, 1] * px + M[1, 1] * py + M[2, 1] * pz
        lz = M[0, 2] * px + M[1, 2] * py + M[2, 2] * pz
        th = np.arctan2(ly, lx)
        rr = np.sqrt(lx * lx + ly * ly)
        RR = R + amp * np.sin(pleats * th)
        return np.sqrt((rr - RR) ** 2 + (lz * flat) ** 2) / flat - r * (0.85 + 0.15 * np.cos(pleats * th))
    F.shape(fn, c - m, c + m, k)


def _shape(self, fn, bmin, bmax, k=0.0, neg=False):
    sl, P = self._region(bmin, bmax)
    if sl is None:
        return
    d = np.broadcast_to(fn(*P), self.D[sl].shape).astype(np.float32)
    self._combine(d, sl, k, neg)


def _displace(self, fn, bmin, bmax, band=0.02):
    sl, P = self._region(bmin, bmax)
    if sl is None:
        return
    D = self.D[sl]
    near = np.abs(D) < band
    d = np.broadcast_to(fn(*P), D.shape)
    D[near] -= d[near]
    self.D[sl] = D


def _shell(self, t):
    """Hollow the solid into cloth of thickness t (keeps the outer surface)."""
    self.D = np.maximum(self.D, -self.D - t)


Field.shape = _shape
Field.shell = _shell
Field.displace = _displace


def halfspace(point, normal):
    p = np.array(point, np.float32); n = np.array(normal, np.float32); n /= np.linalg.norm(n)
    return lambda x, y, z: (x - p[0]) * n[0] + (y - p[1]) * n[1] + (z - p[2]) * n[2]


# ================================================================== materials
def nodes_mat(name):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(bsdf.outputs[0], out.inputs[0])
    return m, nt, bsdf


def N(nt, kind, **inputs):
    n = nt.nodes.new(kind)
    for k, v in inputs.items():
        if k.startswith("_"):
            setattr(n, k[1:], v)
        else:
            n.inputs[k].default_value = v
    return n


def L(nt, a, b):
    nt.links.new(a, b)


def ramp(nt, stops):
    r = nt.nodes.new("ShaderNodeValToRGB")
    els = r.color_ramp.elements
    while len(els) > len(stops):
        els.remove(els[-1])
    while len(els) < len(stops):
        els.new(0.5)
    for e, (pos, col) in zip(els, stops):
        e.position = pos; e.color = (*col, 1) if len(col) == 3 else col
    return r


def mat_skin():
    m, nt, b = nodes_mat("Skin_Greasepaint")
    attr = N(nt, "ShaderNodeVertexColor", _layer_name="makeup")
    tex = N(nt, "ShaderNodeTexCoord")
    # grime and blotches
    grime = N(nt, "ShaderNodeTexNoise", Scale=35.0, Detail=8.0, Roughness=0.65)
    L(nt, tex.outputs["Object"], grime.inputs["Vector"])
    gr = ramp(nt, [(0.35, (1, 1, 1)), (0.75, (0.55, 0.50, 0.42))])
    L(nt, grime.outputs["Fac"], gr.inputs["Fac"])
    mul = N(nt, "ShaderNodeMix", _data_type='RGBA', _blend_type='MULTIPLY', Factor=0.8)
    L(nt, attr.outputs["Color"], mul.inputs[6]); L(nt, gr.outputs["Color"], mul.inputs[7])
    L(nt, mul.outputs[2], b.inputs["Base Color"])
    b.inputs["Subsurface Weight"].default_value = 0.12
    b.inputs["Subsurface Radius"].default_value = (0.9, 0.35, 0.25)
    b.inputs["Subsurface Scale"].default_value = 0.004
    # paint cracks where the paint is thick (alpha = paint mask)
    cr = N(nt, "ShaderNodeTexVoronoi", Scale=260.0, _feature='DISTANCE_TO_EDGE')
    L(nt, tex.outputs["Object"], cr.inputs["Vector"])
    crr = ramp(nt, [(0.0, (0, 0, 0)), (0.06, (1, 1, 1))])
    L(nt, cr.outputs["Distance"], crr.inputs["Fac"])
    pores = N(nt, "ShaderNodeTexNoise", Scale=900.0, Detail=2.0)
    L(nt, tex.outputs["Object"], pores.inputs["Vector"])
    mixh = N(nt, "ShaderNodeMix", _data_type='FLOAT')
    L(nt, attr.outputs["Alpha"], mixh.inputs["Factor"])
    L(nt, pores.outputs["Fac"], mixh.inputs[2]); L(nt, crr.outputs["Color"], mixh.inputs[3])
    bump = N(nt, "ShaderNodeBump", Strength=0.35, Distance=0.0006)
    L(nt, mixh.outputs[0], bump.inputs["Height"])
    L(nt, bump.outputs[0], b.inputs["Normal"])
    rough = N(nt, "ShaderNodeMapRange", **{"From Min": 0.0, "From Max": 1.0, "To Min": 0.62, "To Max": 0.45})
    L(nt, attr.outputs["Alpha"], rough.inputs["Value"])
    L(nt, rough.outputs[0], b.inputs["Roughness"])
    return m


def mat_cloth(name, c1, c2, stripe_scale, base_rough=0.85, axis="X"):
    m, nt, b = nodes_mat(name)
    tex = N(nt, "ShaderNodeTexCoord")
    wave = N(nt, "ShaderNodeTexWave", Scale=stripe_scale, Distortion=1.4, Detail=2.0, _wave_type='BANDS', _bands_direction=axis)
    L(nt, tex.outputs["Object"], wave.inputs["Vector"])
    st = ramp(nt, [(0.48, c1), (0.52, c2)])
    L(nt, wave.outputs["Fac"], st.inputs["Fac"])
    dirt = N(nt, "ShaderNodeTexNoise", Scale=6.0, Detail=10.0, Roughness=0.7)
    L(nt, tex.outputs["Object"], dirt.inputs["Vector"])
    dr = ramp(nt, [(0.38, (1, 1, 1)), (0.72, (0.30, 0.24, 0.16))])
    L(nt, dirt.outputs["Fac"], dr.inputs["Fac"])
    mul = N(nt, "ShaderNodeMix", _data_type='RGBA', _blend_type='MULTIPLY', Factor=1.0)
    L(nt, st.outputs["Color"], mul.inputs[6]); L(nt, dr.outputs["Color"], mul.inputs[7])
    L(nt, mul.outputs[2], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = base_rough
    b.inputs["Sheen Weight"].default_value = 0.4
    weave = N(nt, "ShaderNodeTexNoise", Scale=1400.0, Detail=1.0)
    L(nt, tex.outputs["Object"], weave.inputs["Vector"])
    bump = N(nt, "ShaderNodeBump", Strength=0.25, Distance=0.0005)
    L(nt, weave.outputs["Fac"], bump.inputs["Height"]); L(nt, bump.outputs[0], b.inputs["Normal"])
    return m


def mat_dots(name, base, dot):
    m, nt, b = nodes_mat(name)
    tex = N(nt, "ShaderNodeTexCoord")
    vo = N(nt, "ShaderNodeTexVoronoi", Scale=14.0, Randomness=0.25)
    L(nt, tex.outputs["Object"], vo.inputs["Vector"])
    dr = ramp(nt, [(0.20, dot), (0.23, base)])
    L(nt, vo.outputs["Distance"], dr.inputs["Fac"])
    dirt = N(nt, "ShaderNodeTexNoise", Scale=7.0, Detail=10.0, Roughness=0.7)
    L(nt, tex.outputs["Object"], dirt.inputs["Vector"])
    dd = ramp(nt, [(0.38, (1, 1, 1)), (0.75, (0.25, 0.20, 0.13))])
    L(nt, dirt.outputs["Fac"], dd.inputs["Fac"])
    mul = N(nt, "ShaderNodeMix", _data_type='RGBA', _blend_type='MULTIPLY', Factor=1.0)
    L(nt, dr.outputs["Color"], mul.inputs[6]); L(nt, dd.outputs["Color"], mul.inputs[7])
    L(nt, mul.outputs[2], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.88; b.inputs["Sheen Weight"].default_value = 0.5
    return m


def mat_simple(name, col, rough, **kw):
    m, nt, b = nodes_mat(name)
    b.inputs["Base Color"].default_value = (*col, 1)
    b.inputs["Roughness"].default_value = rough
    for k, v in kw.items():
        b.inputs[k].default_value = v
    return m


def mat_eye():
    m, nt, b = nodes_mat("Eye")
    tex = N(nt, "ShaderNodeTexCoord")
    sep = N(nt, "ShaderNodeSeparateXYZ"); L(nt, tex.outputs["Object"], sep.inputs[0])
    # radial distance from the forward (-Y) axis, in eye-local space
    lx = N(nt, "ShaderNodeMath", _operation='MULTIPLY'); L(nt, sep.outputs[0], lx.inputs[0]); L(nt, sep.outputs[0], lx.inputs[1])
    lz = N(nt, "ShaderNodeMath", _operation='MULTIPLY'); L(nt, sep.outputs[2], lz.inputs[0]); L(nt, sep.outputs[2], lz.inputs[1])
    ad = N(nt, "ShaderNodeMath", _operation='ADD'); L(nt, lx.outputs[0], ad.inputs[0]); L(nt, lz.outputs[0], ad.inputs[1])
    rr = N(nt, "ShaderNodeMath", _operation='SQRT'); L(nt, ad.outputs[0], rr.inputs[0])
    front = N(nt, "ShaderNodeMath", _operation='LESS_THAN'); L(nt, sep.outputs[1], front.inputs[0]); front.inputs[1].default_value = 0
    sc = N(nt, "ShaderNodeMath", _operation='DIVIDE'); L(nt, rr.outputs[0], sc.inputs[0]); sc.inputs[1].default_value = 0.0145
    iris = ramp(nt, [(0.0, (0.0, 0.0, 0.0)), (0.09, (0.0, 0.0, 0.0)), (0.11, (0.62, 0.58, 0.18)),
                     (0.36, (0.35, 0.30, 0.06)), (0.40, (0.05, 0.03, 0.02)), (0.43, (1, 1, 1))])
    L(nt, sc.outputs[0], iris.inputs["Fac"])
    veins = N(nt, "ShaderNodeTexNoise", Scale=180.0, Detail=12.0, Distortion=2.5)
    L(nt, tex.outputs["Object"], veins.inputs["Vector"])
    vr = ramp(nt, [(0.46, (0.80, 0.70, 0.50)), (0.50, (0.55, 0.04, 0.03)), (0.54, (0.78, 0.66, 0.48))])
    L(nt, veins.outputs["Fac"], vr.inputs["Fac"])
    redden = N(nt, "ShaderNodeMix", _data_type='RGBA', _blend_type='MIX')
    L(nt, sc.outputs[0], redden.inputs["Factor"])
    redden.inputs[6].default_value = (0.82, 0.74, 0.55, 1); L(nt, vr.outputs["Color"], redden.inputs[7])
    isw = N(nt, "ShaderNodeMath", _operation='LESS_THAN'); L(nt, sc.outputs[0], isw.inputs[0]); isw.inputs[1].default_value = 0.42
    both = N(nt, "ShaderNodeMath", _operation='MULTIPLY'); L(nt, isw.outputs[0], both.inputs[0]); L(nt, front.outputs[0], both.inputs[1])
    fin = N(nt, "ShaderNodeMix", _data_type='RGBA'); L(nt, both.outputs[0], fin.inputs["Factor"])
    L(nt, redden.outputs[2], fin.inputs[6]); L(nt, iris.outputs["Color"], fin.inputs[7])
    L(nt, fin.outputs[2], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.08
    b.inputs["Coat Weight"].default_value = 1.0
    b.inputs["Subsurface Weight"].default_value = 0.1
    return m


def mat_nose():
    m, nt, b = nodes_mat("Nose_CrackedRubber")
    tex = N(nt, "ShaderNodeTexCoord")
    cr = N(nt, "ShaderNodeTexVoronoi", Scale=140.0, _feature='DISTANCE_TO_EDGE')
    L(nt, tex.outputs["Object"], cr.inputs["Vector"])
    crr = ramp(nt, [(0.0, (0, 0, 0)), (0.08, (1, 1, 1))])
    L(nt, cr.outputs["Distance"], crr.inputs["Fac"])
    col = N(nt, "ShaderNodeMix", _data_type='RGBA'); L(nt, crr.outputs["Color"], col.inputs["Factor"])
    col.inputs[6].default_value = (0.08, 0.01, 0.01, 1); col.inputs[7].default_value = (0.42, 0.012, 0.015, 1)
    L(nt, col.outputs[2], b.inputs["Base Color"])
    bump = N(nt, "ShaderNodeBump", Strength=0.6, Distance=0.0008)
    L(nt, crr.outputs["Color"], bump.inputs["Height"]); L(nt, bump.outputs[0], b.inputs["Normal"])
    b.inputs["Roughness"].default_value = 0.22
    b.inputs["Coat Weight"].default_value = 0.6
    return m


# ================================================================== makeup (vertex paint)
def paint_makeup(o):
    me = o.data
    n = len(me.vertices)
    co = np.empty(n * 3, np.float32); me.vertices.foreach_get("co", co); co = co.reshape(-1, 3)
    x, y, z = co[:, 0], co[:, 1], co[:, 2]
    sick = np.array([0.50, 0.53, 0.45]); white = np.array([0.86, 0.85, 0.80])
    col = np.tile(sick, (n, 1)); alpha = np.zeros(n)
    # white greasepaint over head and neck, feathered
    w = np.clip((z - 1.60) / 0.06, 0, 1) * (y < 0.06 + 0.4 * (z - 1.62)).astype(float)
    w = np.maximum(w, np.clip((z - 1.70) / 0.03, 0, 1))
    col = col * (1 - w[:, None]) + white * w[:, None]; alpha = np.maximum(alpha, w * 0.9)
    # black diamonds over the eyes, with drips
    for sx in (1, -1):
        ex, ez = sx * 0.034, 1.836
        dia = np.abs(x - ex) / 0.024 + np.abs(z - ez) / 0.062
        front = y < -0.04
        m = np.clip((1.0 - dia) / 0.08, 0, 1) * front
        for k in range(4):                                         # drips running down the cheek
            dx = ex + sx * (-0.010 + 0.007 * k)
            drip = (np.abs(x - dx) < 0.0016 + 0.0006 * (k % 2)) & (z < ez - 0.02) & (z > ez - 0.05 - 0.012 * k) & front
            m = np.maximum(m, drip.astype(float))
        col = col * (1 - m[:, None]) + np.array([0.02, 0.02, 0.03]) * m[:, None]
    # red smeared grin, wider than the cut and pulled up the cheeks
    P = np.array([[p.x, p.y, p.z] for p in A.MOUTH])
    d = np.full(n, 9.0)
    for a, b in zip(P, P[1:]):
        ab = b - a; t = np.clip(((co - a) @ ab) / (ab @ ab), 0, 1)
        d = np.minimum(d, np.linalg.norm(co - (a + t[:, None] * ab), axis=1))
    smear = np.array([noise.noise(Vector((px * 90, py * 90, pz * 90))) for px, py, pz in co[d < 0.03]]) if np.any(d < 0.03) else np.array([])
    jitter = np.zeros(n); jitter[d < 0.03] = smear * 0.006
    corner = np.clip((np.abs(x) - 0.03) / 0.04, 0, 1)
    m = np.clip((0.012 + 0.006 * corner - d + jitter) / 0.003, 0, 1) * (y < -0.03)
    col = col * (1 - m[:, None]) + np.array([0.36, 0.015, 0.02]) * m[:, None]
    # dirty, bruised fingertips and toes, darker joints
    tips = np.zeros(n)
    for p, dirn, _ in A.NAILS:
        dd = np.linalg.norm(co - np.array(p), axis=1)
        tips = np.maximum(tips, np.clip((0.03 - dd) / 0.03, 0, 1))
    col = col * (1 - 0.55 * tips[:, None]) + np.array([0.25, 0.12, 0.10]) * 0.55 * tips[:, None]
    attr = me.color_attributes.new("makeup", 'FLOAT_COLOR', 'POINT')
    rgba = np.concatenate([col, alpha[:, None]], axis=1).astype(np.float32)
    attr.data.foreach_set("color", rgba.ravel())


# ================================================================== geometry
def build_body(coll):
    F = A.body_field(h=0.0032 if QUICK else 0.0019)
    o = field_object(F, "Clown_Body", coll, iters=2)
    paint_makeup(o)
    return o, F


def build_face_parts(coll, mats):
    out = []
    for i, (c, r) in enumerate(A.EYES):
        bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24, radius=r, location=c)
        e = bpy.context.object; e.name = f"Eye_{'LR'[i]}"
        e.rotation_euler = (0, 0, math.radians(8 if c.x > 0 else -8))        # a slight wall-eyed stare
        bpy.ops.object.shade_smooth(); e.data.materials.append(mats["eye"]); out.append(link(e, coll))
    mid = A.MOUTH[len(A.MOUTH) // 2]
    bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=24, radius=0.0185, location=(0, -0.117, 1.797))
    nose = bpy.context.object; nose.name = "Nose"; nose.scale = (1.0, 0.95, 0.92)
    bpy.ops.object.shade_smooth(); nose.data.materials.append(mats["nose"]); out.append(link(nose, coll))
    # teeth: two rows of needle teeth, a few missing or broken
    verts, faces = [], []

    def cone(base, tip, r, seg=7):
        axis = (tip - base).normalized()
        u = axis.orthogonal().normalized(); v = axis.cross(u)
        i0 = len(verts)
        for s in range(seg):
            a = 2 * math.pi * s / seg
            verts.append(base + (u * math.cos(a) + v * math.sin(a)) * r)
        verts.append(tip.copy()); verts.append(base - axis * r * 0.5)
        for s in range(seg):
            faces.append((i0 + s, i0 + (s + 1) % seg, i0 + seg))
            faces.append((i0 + (s + 1) % seg, i0 + s, i0 + seg + 1))
    rnd = random.Random(3)
    for i in range(1, len(A.MOUTH) - 1, 1):
        p, op = A.MOUTH[i], A.OPEN[i]
        if op < 0.0024:
            continue
        for sgn in (1, -1):
            if rnd.random() < 0.12:
                continue                                        # missing tooth
            base = p + Vector((rnd.uniform(-0.001, 0.001), 0.0045, sgn * (op + 0.0005)))
            L_ = op * rnd.uniform(1.0, 1.9) * (0.5 if rnd.random() < 0.15 else 1.0)
            tip = base + Vector((rnd.uniform(-0.0012, 0.0012), rnd.uniform(-0.001, 0.0015), -sgn * L_))
            cone(base, tip, rnd.uniform(0.0019, 0.0026))
    me = bpy.data.meshes.new("Teeth"); me.from_pydata([tuple(v) for v in verts], [], faces); me.update()
    t = bpy.data.objects.new("Teeth", me); coll.objects.link(t); t.data.materials.append(mats["teeth"]); out.append(t)
    # long cracked nails
    verts, faces = [], []
    for p, dirn, inward in A.NAILS:
        base = Vector(p) - dirn * 0.010 - inward * 0.004
        tip = Vector(p) + dirn * 0.020 + inward * 0.006
        cone(base, tip, 0.0058, seg=10)
    me = bpy.data.meshes.new("Nails"); me.from_pydata([tuple(v) for v in verts], [], faces); me.update()
    nails = bpy.data.objects.new("Nails", me); coll.objects.link(nails); nails.data.materials.append(mats["nails"])
    nails.data.shade_smooth(); out.append(nails)
    return out


def build_hair(coll, mats, F):
    rnd = random.Random(11)
    cu = bpy.data.curves.new("Hair", 'CURVE'); cu.dimensions = '3D'
    cu.bevel_depth = 0.0007; cu.bevel_resolution = 1
    C, R = Vector((0, 0.012, 1.868)), Vector((0.080, 0.100, 0.083))
    count = 0
    while count < (90 if QUICK else 320):
        th = rnd.uniform(0, 2 * math.pi); ph = rnd.uniform(0.15, 1.1)
        n = Vector((math.cos(th) * math.cos(ph), math.sin(th) * math.cos(ph), math.sin(ph)))
        if n.y < -0.25 or abs(n.x) < 0.45 and n.z > 0.55:          # bald crown and face stay clear
            continue
        p = Vector((C.x + R.x * n.x, C.y + R.y * n.y, C.z + R.z * n.z)) - n * 0.002
        sp = cu.splines.new('POLY'); pts = 9; sp.points.add(pts - 1)
        d = (n + Vector((0, 0.3, -0.2))).normalized()
        L_ = rnd.uniform(0.05, 0.16)
        for k in range(pts):
            sp.points[k].co = (*p, 1)
            d = (d + Vector((rnd.uniform(-.3, .3), rnd.uniform(-.2, .3), -0.18))).normalized()
            p = p + d * (L_ / pts)
        count += 1
    o = bpy.data.objects.new("Hair", cu); coll.objects.link(o)
    o.data.materials.append(mats["hair"])
    return o


def build_costume(coll, mats):
    h = 0.006 if QUICK else 0.0035
    out = []
    # ---- pants: balloon legs bunched at the ankle
    P = Field((-0.30, -0.22, 0.10), (0.30, 0.20, 1.20), h)
    P.ell((0, 0.012, 1.02), (0.175, 0.125, 0.13), k=0.04)
    for sx in (1, -1):
        hp, kn, an = (Vector((v[0] * sx, v[1], v[2])) for v in (A.HIP, A.KNEE, A.ANKLE))
        P.cap(hp, kn, 0.105, 0.088, k=0.05)
        P.cap(kn, an + Vector((0, 0, 0.09)), 0.088, 0.072, k=0.04)
        P.ell(an + Vector((0, 0, 0.10)), (0.082, 0.082, 0.05), k=0.03)          # bunched cuff
    P.shape(halfspace((0, 0, 1.125), (0, 0, 1)), (-0.4, -0.3, 1.1), (0.4, 0.3, 1.25), k=0.006, neg=True)
    P.shape(halfspace((0, 0, 0.165), (0, 0, -1)), (-0.4, -0.3, 0.05), (0.4, 0.3, 0.2), k=0.004, neg=True)
    P.displace(lambda x, y, z: 0.006 * np.sin(55 * z + 6 * np.sin(18 * x)) * np.clip((0.62 - z) / 0.3, 0, 1)
               + 0.0035 * np.sin(31 * z + 9 * np.cos(14 * y)), (-0.4, -0.3, 0.1), (0.4, 0.3, 1.2))
    pants = field_object(P, "Pants", coll); pants.data.materials.append(mats["pants"]); out.append(pants)

    # ---- shirt: open, torn front that shows the ribs; sleeves cut mid-forearm
    S = Field((-0.62, -0.20, 0.98), (0.62, 0.18, 1.66), h)
    S.ell((0, 0.010, 1.40), (0.158, 0.118, 0.175), k=0.05)
    S.ell((0, 0.012, 1.525), (0.208, 0.100, 0.072), k=0.05)
    S.ell((0, 0.012, 1.17), (0.132, 0.100, 0.14), k=0.05)
    for sx in (1, -1):
        s, e, w, d = A.arm_points(sx)
        S.cap(s, e, 0.062, 0.054, k=0.05)
        cut = e + d * 0.17
        S.cap(e, cut + d * 0.04, 0.054, 0.058, k=0.03)
        S.shape(halfspace(cut, d), cut - Vector((0.15, 0.15, 0.15)), cut + Vector((0.15, 0.15, 0.15)), k=0.003, neg=True)
    S.shape(halfspace((0, 0, 1.03), (0, 0, -1)), (-0.4, -0.3, 0.9), (0.4, 0.3, 1.1), k=0.004, neg=True)
    S.shell(0.010)
    # torn opening: a V down the chest with ragged bites along the edge
    S.ell((0, -0.16, 1.38), (0.072, 0.10, 0.22), rot=(0, 0, 0), k=0.01, neg=True)
    rnd = random.Random(5)
    for i in range(26):
        z = rnd.uniform(1.12, 1.56); sx = rnd.choice((1, -1))
        wv = 0.072 * math.sqrt(max(0, 1 - ((z - 1.38) / 0.22) ** 2))
        S.ell((sx * (wv + rnd.uniform(-0.004, 0.012)), -0.11, z), (rnd.uniform(0.006, 0.016), 0.06, rnd.uniform(0.004, 0.012)),
              rot=(0, rnd.uniform(-40, 40), 0), k=0.003, neg=True)
    S.displace(lambda x, y, z: 0.0018 * np.sin(38 * z + 7 * np.sin(21 * x) + 4 * np.cos(17 * y))
               + 0.0014 * np.sin(29 * x - 23 * z + 5 * np.sin(13 * z)),
               (-0.7, -0.3, 0.9), (0.7, 0.3, 1.7))
    shirt = field_object(S, "Shirt", coll); shirt.data.materials.append(mats["shirt"]); out.append(shirt)

    # ---- ruff collar and wrist frills
    R = Field((-0.20, -0.20, 1.50), (0.20, 0.20, 1.68), h * 0.8)
    torus_frill(R, (0, 0.006, 1.588), (0, -0.25, 1), 0.098, 0.022, 26, 0.014)
    torus_frill(R, (0, 0.006, 1.612), (0, -0.25, 1), 0.080, 0.018, 22, 0.012)
    ruff = field_object(R, "Ruff", coll, iters=1); ruff.data.materials.append(mats["ruff"]); out.append(ruff)
    for sx in (1, -1):
        s, e, w, d = A.arm_points(sx)
        c = e + d * 0.175
        Rf = Field(tuple(c - Vector((0.12,) * 3)), tuple(c + Vector((0.12,) * 3)), h * 0.8)
        torus_frill(Rf, c, d, 0.062, 0.014, 18, 0.010)
        f = field_object(Rf, f"Cuff_{'LR'[sx < 0]}", coll, iters=1); f.data.materials.append(mats["ruff"]); out.append(f)

    # ---- shoes: long, swollen, worn
    for sx in (1, -1):
        an = Vector((A.ANKLE[0] * sx, A.ANKLE[1], A.ANKLE[2]))
        Sh = Field((an.x - 0.13, -0.42, -0.01), (an.x + 0.13, 0.12, 0.22), h)
        Sh.ell(an + Vector((0, -0.07, -0.040)), (0.068, 0.15, 0.058), k=0.03)
        Sh.ell(an + Vector((sx * 0.006, -0.23, -0.032)), (0.080, 0.085, 0.062), k=0.05)
        Sh.cap(an + Vector((0, 0.01, -0.02)), an + Vector((0, 0.01, 0.075)), 0.06, 0.055, k=0.03)
        Sh.shape(halfspace((0, 0, 0.004), (0, 0, -1)), (an.x - 0.2, -0.5, -0.05), (an.x + 0.2, 0.2, 0.02), k=0.004, neg=True)
        sh = field_object(Sh, f"Shoe_{'LR'[sx < 0]}", coll); sh.data.materials.append(mats["shoe"]); out.append(sh)
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=4, radius=0.026, location=an + Vector((sx * 0.006, -0.25, 0.034)))
        pp = bpy.context.object; pp.name = f"Pompom_Shoe_{'LR'[sx < 0]}"; link(pp, coll)
        d = pp.modifiers.new("fuzz", 'DISPLACE'); d.strength = 0.006
        d.texture = bpy.data.textures.get("fuzz") or bpy.data.textures.new("fuzz", 'CLOUDS'); d.texture.noise_scale = 0.004
        pp.data.materials.append(mats["pompom"]); bpy.ops.object.shade_smooth(); out.append(pp)
    # three pompoms down the left flap of the shirt
    for i, z in enumerate((1.48, 1.38, 1.28)):
        x = -0.095 - 0.01 * i
        y = front_y(S, x, z, y0=-0.2, y1=0.05)
        if y is None:
            continue
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=4, radius=0.022, location=(x, y - 0.010, z))
        pp = bpy.context.object; pp.name = f"Pompom_Shirt_{i}"; link(pp, coll)
        d = pp.modifiers.new("fuzz", 'DISPLACE'); d.strength = 0.005; d.texture = bpy.data.textures["fuzz"]
        pp.data.materials.append(mats["pompom"]); bpy.ops.object.shade_smooth(); out.append(pp)
    return out


# ================================================================== scene
def build_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    mats = {
        "skin": mat_skin(), "eye": mat_eye(), "nose": mat_nose(),
        "teeth": mat_simple("Teeth", (0.55, 0.45, 0.28), 0.32, **{"Subsurface Weight": 0.2}),
        "nails": mat_simple("Nails", (0.30, 0.26, 0.15), 0.35, **{"Coat Weight": 0.4}),
        "hair": mat_simple("Hair", (0.32, 0.07, 0.025), 0.55, **{"Sheen Weight": 0.5}),
        "pants": mat_cloth("Pants_Stripes", (0.42, 0.05, 0.04), (0.58, 0.52, 0.40), 9.0),
        "shirt": mat_dots("Shirt_Dots", (0.40, 0.29, 0.08), (0.20, 0.02, 0.02)),
        "ruff": mat_cloth("Ruff_Linen", (0.70, 0.66, 0.56), (0.62, 0.58, 0.48), 3.0, 0.9),
        "shoe": mat_simple("Shoe_Leather", (0.16, 0.02, 0.02), 0.38, **{"Coat Weight": 0.3}),
        "pompom": mat_simple("Pompom", (0.40, 0.02, 0.03), 0.95, **{"Sheen Weight": 1.0}),
    }
    anat = new_coll("Anatomy"); face = new_coll("Face"); cost = new_coll("Costume")
    body, F = build_body(anat)
    body.data.materials.append(mats["skin"])
    build_face_parts(face, mats)
    build_hair(face, mats, F)
    build_costume(cost, mats)
    return mats


if __name__ == "__main__":
    build_scene()
    path = os.path.join(HERE, "clown.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path, compress=True)
    print("saved", path)
