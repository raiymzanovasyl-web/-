"""Clown v4, after the client's concept: harlequin costume (yellow polka dots | navy-cream stripes),
puffed blouse with frilled cuffs and red pompoms, gathered bloomers, striped socks, laced boots,
layered ruff, red curly hair, an axe. Two skins (bloody / clean), ~200k triangles, Unity texture sets.
python clown4.py <reference_mask.fbx> [preview|full]"""
import math, os, sys
import numpy as np
import bpy, bmesh
from mathutils import Vector, Matrix, Quaternion
from scipy import ndimage

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
MASK = sys.argv[1]; MODE = sys.argv[2] if len(sys.argv) > 2 else "preview"
sys.argv = [sys.argv[0], MASK, "lib"]
import clown3 as C3
B, BR, A, Hd = C3.B, C3.BR, C3.A, C3.Hd
from sdf import Field, front_y
QUICK = MODE in ("preview", "fullquick")
C3.QUICK = QUICK
OUT = os.path.join(HERE, "v4") if MODE != "fullquick" else os.environ.get("V4_TMP", "/tmp/v4q")
rng = np.random.default_rng(21)

YELLOW, NAVY, CREAM, INK = np.array([0.56, 0.37, 0.05]), np.array([0.045, 0.06, 0.15]), np.array([0.66, 0.58, 0.44]), np.array([0.025, 0.02, 0.02])
RED, ORANGE, BROWN = np.array([0.42, 0.025, 0.025]), np.array([0.62, 0.22, 0.04]), np.array([0.10, 0.05, 0.03])


# ================================================================== fabric colour, painted per vertex
def verts(o):
    return C3.verts(o)


def put(o, name, rgb):
    a = o.data.color_attributes.new(name, 'FLOAT_COLOR', 'POINT')
    a.data.foreach_set("color", np.concatenate([rgb, np.ones((len(rgb), 1))], 1).astype(np.float32).ravel())


def dots(co, cell, r, jitter=0.25, seed=0):
    g = np.floor(co / cell)
    h = np.sin(g @ np.array([12.9898, 78.233, 37.719]) + seed) * 43758.5453
    off = (np.stack([np.modf(h)[0], np.modf(h * 1.7)[0], np.modf(h * 2.3)[0]], 1) - 0.5) * jitter
    c = (g + 0.5 + off) * cell
    return np.linalg.norm(co - c, axis=1) < r


def stripes_around(co, centre_xy, n):
    th = np.arctan2(co[:, 1] - centre_xy[1], co[:, 0] - centre_xy[0])
    return np.sin(th * n) > 0


def stripes_along_arm(co, sx, n):
    s, e, w, d = A.arm_points(sx)
    rel = co - np.array(s)
    t = rel @ np.array(d)
    radial = rel - np.outer(t, np.array(d))
    up = np.array([0, 0, 1.0]); u = up - np.array(d) * np.dot(up, np.array(d)); u /= np.linalg.norm(u)
    v = np.cross(np.array(d), u)
    th = np.arctan2(radial @ v, radial @ u)
    return np.sin(th * n) > 0


def harlequin(co, dot_cell, dot_r, n_torso, n_leg=None):
    x = co[:, 0]
    col = np.empty_like(co)
    yellow = x < 0                              # the character's right side (viewer's left)
    d = dots(co, dot_cell, dot_r)
    col[yellow] = np.where(d[yellow, None], INK, YELLOW)
    st = stripes_around(co, (0, 0.0), n_torso)
    if n_leg:
        for sx in (1, -1):
            leg = (co[:, 2] < 0.98) & (x * sx > 0)
            st[leg] = stripes_around(co[leg], (sx * A.HIP[0], 0.0), n_leg)
    for sx in (1, -1):
        arm = x * sx > 0.24
        st[arm] = stripes_along_arm(co[arm], sx, 10)
    navy = ~yellow
    col[navy] = np.where(st[navy, None], NAVY, CREAM)
    return col


# ================================================================== geometry
def puff_top(F, coll, mats):
    S = C3.cloth_from_body(F, (-0.78, -0.42, 0.95), (0.78, 0.34, 1.66), 0.020, 0.024)
    X, Y, Z = C3.grid(S)
    T = Field(tuple(S.lo), tuple(S.lo + S.h * (S.n - 1)), S.h); T.n = S.n.copy(); T.D = np.full(tuple(S.n), 0.05, np.float32)
    for sx in (1, -1):                                # puffed sleeves gathered at the wrist
        s, e, w, d = A.arm_points(sx)
        T.cap(s + d * 0.05, e, 0.092, 0.098, k=0.0)
        T.cap(e, w - d * 0.07, 0.098, 0.086, k=0.0)
        T.cap(w - d * 0.07, w - d * 0.025, 0.086, 0.052, k=0.0)
    kk = 0.05; hh = np.clip(0.5 + 0.5 * (S.D - T.D) / kk, 0, 1)
    S.D = (S.D * (1 - hh) + T.D * hh - kk * hh * (1 - hh)).astype(np.float32)
    S.D = np.maximum(S.D, 0.120 - np.sqrt(X ** 2 + (Y - 0.015) ** 2) - np.clip((1.560 - Z) * 4, 0, None))
    S.D = np.maximum(S.D, Z - 1.605)
    S.D = np.maximum(S.D, 0.990 - Z)
    for sx in (1, -1):
        t, s, e, w, d = C3.arm_axis_terms(X, Y, Z, sx)
        side = X * sx > 0.18
        S.D = np.where(side, np.maximum(S.D, t - (A.UPPER + A.FORE - 0.028)), S.D)
        ang = np.arctan2(Z - (s.z + d.z * t), Y - (s.y + d.y * t))
        gather = np.clip((t - (A.UPPER + A.FORE - 0.16)) / 0.12, 0, 1)        # pleats pulled into the cuff
        elbow = np.exp(-((t - A.UPPER) / 0.06) ** 2)
        S.D = np.where(side & (np.abs(S.D) < 0.025), S.D - 0.0055 * np.sin(ang * 14 + t * 8) * gather
                       - 0.003 * np.sin(t * 120 + 2.5 * np.sin(ang * 2)) * elbow, S.D)
    belly = np.exp(-((Z - 1.16) / 0.12) ** 2) * (Y < -0.05)
    shoulder = np.exp(-((Z - 1.48) / 0.08) ** 2) * (np.abs(X) > 0.12) * (np.abs(X) < 0.30)
    S.D = np.where(np.abs(S.D) < 0.025, S.D - (0.0030 * np.sin(Z * 70 + 8 * np.sin(X * 12)) * belly
                                               + 0.0025 * np.sin(X * 45 - Z * 30) * shoulder
                                               + 0.0018 * np.sin(np.arctan2(Y, X) * 11 + Z * 15) * (Z < 1.08)), S.D).astype(np.float32)
    S.shell(0.006)
    o = B.field_object(S, "Top", coll, iters=2); o.data.materials.append(mats["fabric"])
    co = verts(o)
    put(o, "fabric", harlequin(co, 0.045, 0.009, 18))
    return o, S


def bloomers(F, coll, mats):
    P = C3.cloth_from_body(F, (-0.42, -0.42, 0.18), (0.42, 0.32, 1.16), 0.022, 0.030)
    X, Y, Z = C3.grid(P)
    T = Field(tuple(P.lo), tuple(P.lo + P.h * (P.n - 1)), P.h); T.n = P.n.copy(); T.D = np.full(tuple(P.n), 0.05, np.float32)
    for sx in (1, -1):
        hp, kn, an = (Vector((v[0] * sx, v[1], v[2])) for v in (A.HIP, A.KNEE, A.ANKLE))
        T.cap(hp - Vector((0, 0, 0.12)), kn, 0.150, 0.148, k=0.0)
        T.cap(kn, an + Vector((0, 0, 0.24)), 0.148, 0.120, k=0.0)
        T.cap(an + Vector((0, 0, 0.24)), an + Vector((0, 0.005, 0.145)), 0.120, 0.068, k=0.0)
        T.ell(an + Vector((0, 0.005, 0.140)), (0.072, 0.072, 0.014), k=0.0)          # elastic band
    kk = 0.06; hh = np.clip(0.5 + 0.5 * (P.D - T.D) / kk, 0, 1)
    P.D = (P.D * (1 - hh) + T.D * hh - kk * hh * (1 - hh)).astype(np.float32)
    # waist sash hugging the belly line
    G = C3.cloth_from_body(F, (-0.42, -0.42, 0.18), (0.42, 0.32, 1.16), 0.022, 0.034)
    n = np.array([0, -0.27, 0.963]); n /= np.linalg.norm(n)
    plane = X * n[0] + (Y + 0.20) * n[1] + (Z - 1.005) * n[2]
    sash = np.maximum(G.D, np.abs(plane + 0.020) - 0.028)
    P.D = np.minimum(np.maximum(P.D, plane), sash)
    P.D = np.maximum(P.D, (an.z if False else 0.0) + 0.222 - Z)
    ang = np.stack([np.arctan2(Y - 0.02, X - sx * A.HIP[0]) for sx in (1, -1)])
    angl = np.where(X > 0, ang[0], ang[1])
    gath = np.exp(-((Z - 0.30) / 0.08) ** 2)
    knee = np.exp(-((Z - 0.52) / 0.07) ** 2)
    waist = np.exp(-((Z - 1.04) / 0.05) ** 2)
    P.D = np.where(np.abs(P.D) < 0.025, P.D - (0.0065 * np.sin(angl * 16 + Z * 10) * gath
                                               + 0.0035 * np.sin(Z * 90 + 3 * np.sin(angl * 3)) * knee * (Y > -0.03)
                                               + 0.0030 * np.sin(angl * 22) * waist
                                               + 0.0022 * np.sin(angl * 6 + Z * 11 + 2 * np.sin(Z * 7))), P.D).astype(np.float32)
    P.shell(0.006)
    o = B.field_object(P, "Pants", coll, iters=2); o.data.materials.append(mats["fabric"])
    co = verts(o)
    col = harlequin(co, 0.085, 0.024, 18, n_leg=16)
    pl = co[:, 0] * n[0] + (co[:, 1] + 0.20) * n[1] + (co[:, 2] - 1.005) * n[2]
    col[np.abs(pl + 0.020) < 0.030] = ORANGE
    put(o, "fabric", col)
    return o, P


def ruff(coll, mats):
    R = Field((-0.30, -0.30, 1.48), (0.30, 0.30, 1.72), 0.0022 if not QUICK else 0.004)
    layers = [(1.585, 0.180, 0.030, 36, 0.022), (1.607, 0.152, 0.028, 32, 0.019), (1.628, 0.124, 0.024, 28, 0.016)]
    for z, Rr, r, n, amp in layers:
        B.torus_frill(R, (0, 0.012, z), (0, -0.10, 1), Rr, r, n, amp)
    o = B.field_object(R, "Ruff", coll, iters=1); o.data.materials.append(mats["fabric"])
    co = verts(o); rad = np.hypot(co[:, 0], co[:, 1] - 0.012)
    col = np.tile(CREAM * 1.1, (len(co), 1))
    for z, Rr, r, n, amp in layers:
        near = np.abs(co[:, 2] - z) < 0.016
        col[near & (rad > Rr + amp + r * 0.75)] = RED
    put(o, "fabric", col)
    return o


def cuffs(coll, mats):
    out = []
    for sx in (1, -1):
        s, e, w, d = A.arm_points(sx)
        G = Field(tuple(w - Vector((0.14,) * 3)), tuple(w + Vector((0.14,) * 3)), 0.0020 if not QUICK else 0.004)
        B.torus_frill(G, w - d * 0.045, d, 0.072, 0.016, 22, 0.014, flat=1.3)
        B.torus_frill(G, w - d * 0.020, d, 0.064, 0.014, 20, 0.012, flat=1.3)
        o = B.field_object(G, f"Cuff_{'LR'[sx < 0]}", coll, iters=1); o.data.materials.append(mats["fabric"])
        co = verts(o); t = (co - np.array(w)) @ np.array(d)
        rad = np.linalg.norm((co - np.array(w)) - np.outer(t, np.array(d)), axis=1)
        col = np.tile(CREAM * 1.1, (len(co), 1)); col[rad > 0.074] = RED
        put(o, "fabric", col); out.append(o)
    return out


def boots(coll, mats):
    out = []
    for sx in (1, -1):
        an = Vector((A.ANKLE[0] * sx, A.ANKLE[1], A.ANKLE[2]))
        G = Field((an.x - 0.17, -0.50, -0.01), (an.x + 0.17, 0.16, 0.30), 0.0028 if not QUICK else 0.005)
        G.ell(an + Vector((0, -0.080, -0.045)), (0.095, 0.170, 0.070), k=0.04)
        G.ell(an + Vector((sx * 0.010, -0.265, -0.032)), (0.110, 0.110, 0.082), k=0.07)          # swollen toe
        G.cap(an + Vector((0, 0.012, -0.03)), an + Vector((0, 0.010, 0.120)), 0.085, 0.078, k=0.05)  # shaft
        G.ell(an + Vector((0, -0.090, -0.090)), (0.112, 0.215, 0.016), k=0.012)                  # sole
        G.shape(B.halfspace((0, 0, 0.004), (0, 0, -1)), (an.x - 0.3, -0.6, -0.05), (an.x + 0.3, 0.3, 0.02), k=0.003, neg=True)
        laces = []
        for i in range(6):                                                                       # criss-cross laces
            z = an.z + 0.115 - i * 0.030; y = an.y - 0.060 - i * 0.022
            yf = front_y(G, an.x, z, y0=-0.5, y1=0.2)
            if yf is None:
                continue
            l = Vector((an.x - 0.032, yf - 0.002, z)); r = Vector((an.x + 0.032, yf - 0.002, z))
            laces.append((l, r))
        for (l0, r0), (l1, r1) in zip(laces, laces[1:]):
            G.cap(l0, r1, 0.0045, k=0.003); G.cap(r0, l1, 0.0045, k=0.003)
        for l, r in laces:
            G.ell(l, (0.006,) * 3, k=0.002); G.ell(r, (0.006,) * 3, k=0.002)
        o = B.field_object(G, f"Boot_{'LR'[sx < 0]}", coll, iters=1); o.data.materials.append(mats["leather"])
        co = verts(o)
        col = np.tile(np.array([0.30, 0.025, 0.02]), (len(co), 1))
        col[co[:, 2] < 0.022] = BROWN
        lace = np.zeros(len(co), bool)
        for l, r in laces:
            seg = np.array(r) - np.array(l)
            lace |= (np.abs(co[:, 1] - l.y) < 0.010) & (np.abs(co[:, 2] - l.z) < 0.04) & (np.abs(co[:, 0] - an.x) < 0.04) & (co[:, 1] < l.y + 0.004)
        col[lace] = np.array([0.45, 0.32, 0.16])
        put(o, "fabric", col); out.append(o)
    return out


def pompoms(S, coll, mats):
    out = []
    for i, z in enumerate((1.46, 1.31, 1.16)):
        yf = front_y(S, 0.0, z, y0=-0.45, y1=0.2)
        if yf is None:
            continue
        G = Field((-0.06, yf - 0.09, z - 0.06), (0.06, yf + 0.03, z + 0.06), 0.0016 if not QUICK else 0.003)
        G.ell((0.0, yf - 0.030, z), (0.038, 0.034, 0.038), k=0.0)
        X, Y, Zz = C3.grid(G)
        G.D = (G.D - 0.004 * np.sin(X * 600) * np.sin(Y * 560) * np.sin(Zz * 640)).astype(np.float32)
        o = B.field_object(G, f"Pompom_{i}", coll, iters=1); o.data.materials.append(mats["fabric"])
        put(o, "fabric", np.tile(RED * 1.1, (len(o.data.vertices), 1))); out.append(o)
    return out


def hair(coll, mats):
    G = Field((-0.24, -0.10, 1.66), (0.24, 0.24, 2.02), 0.0022 if not QUICK else 0.004)
    for sx in (1, -1):
        c = np.array([sx * 0.130, 0.035, 1.855]); semi = np.array([0.075, 0.095, 0.085])
        placed = 0
        while placed < (420 if not QUICK else 150):
            p = c + rng.uniform(-1, 1, 3) * semi
            if p[1] < -0.05 or np.sum(((p - c) / semi) ** 2) > 1.0:
                continue
            G.ell(tuple(p), tuple(rng.uniform(0.007, 0.015, 3)), rot=tuple(rng.uniform(0, 180, 3)), k=0.006)
            placed += 1
    for _ in range(80 if not QUICK else 30):                                   # thinner fringe round the back
        a = rng.uniform(-1.2, 1.2)
        p = np.array([0.12 * math.sin(a), 0.05 + 0.10 * math.cos(a), 1.80 + rng.uniform(-0.02, 0.06)])
        G.ell(tuple(p), tuple(rng.uniform(0.010, 0.018, 3)), rot=tuple(rng.uniform(0, 180, 3)), k=0.008)
    X, Y, Z = C3.grid(G)
    curl = 0.0035 * np.sin(X * 420 + 3 * np.sin(Z * 300)) * np.sin(Y * 390 + 2 * np.sin(X * 260)) * np.sin(Z * 450)
    G.D = np.where(np.abs(G.D) < 0.01, G.D - curl, G.D).astype(np.float32)
    o = B.field_object(G, "Hair", coll, iters=1); o.data.materials.append(mats["hair"])
    return o


def axe(coll, mats):
    """A short fire axe, ~250 vertices, gripped in the right hand."""
    s, e, w, d = A.arm_points(-1)
    inward, across = A.hand_frame(-1, d)
    grip = w + d * 0.060 + inward * 0.030
    hd = (d * 0.35 + Vector((0.0, -0.25, -1.0))).normalized()   # hangs from the fist, head by the thigh
    bm = bmesh.new()
    seg = 8; L = 0.50
    base = grip - hd * 0.06
    ring = []
    for k in range(5):
        t = k / 4; c = base + hd * (L * t); r = 0.017 - 0.003 * t
        u = hd.orthogonal().normalized(); v = hd.cross(u)
        ring.append([bm.verts.new(c + (u * math.cos(2 * math.pi * j / seg) + v * math.sin(2 * math.pi * j / seg)) * r) for j in range(seg)])
    for a_, b_ in zip(ring, ring[1:]):
        for j in range(seg):
            bm.faces.new((a_[j], a_[(j + 1) % seg], b_[(j + 1) % seg], b_[j]))
    bm.faces.new(list(reversed(ring[0]))); bm.faces.new(ring[-1])
    me = bpy.data.meshes.new("Axe_Handle"); bm.to_mesh(me); bm.free()
    handle = bpy.data.objects.new("Axe_Handle", me); coll.objects.link(handle); me.materials.append(mats["wood"])
    # head: blade profile extruded, blade edge facing forward
    top = base + hd * L
    fwd = Vector((0, -1, 0)); fwd = (fwd - hd * fwd.dot(hd)).normalized(); side = hd.cross(fwd).normalized()
    top = base + hd * L
    prof = [(-0.035, -0.020), (0.040, -0.030), (0.120, -0.075), (0.135, -0.010), (0.130, 0.055), (0.120, 0.075),
            (0.040, 0.028), (-0.035, 0.022), (-0.070, 0.010), (-0.070, -0.010)]
    bm = bmesh.new()
    lay = []
    for th in (-0.011, 0.011):
        lay.append([bm.verts.new(top - hd * 0.03 + fwd * px + hd * py + side * th * (0.25 if 0.10 < px else 1.0)) for px, py in prof])
    bm.faces.new(lay[0]); bm.faces.new(list(reversed(lay[1])))
    n = len(prof)
    for j in range(n):
        bm.faces.new((lay[0][j], lay[1][j], lay[1][(j + 1) % n], lay[0][(j + 1) % n]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new("Axe_Head"); bm.to_mesh(me); bm.free()
    head = bpy.data.objects.new("Axe_Head", me); coll.objects.link(head); me.materials.append(mats["steel"])
    for o in (handle, head):
        co = verts(o)
        blood = np.clip(((co - np.array(top)) @ np.array(hd) + 0.10) / 0.10, 0, 1) * (0.5 + 0.5 * np.sin(co[:, 0] * 400) ** 2)
        C3.set_attr(o, "blood", blood)
        put(o, "fabric", np.ones((len(co), 3)))
    return [handle, head]


# ================================================================== makeup and socks
def repaint_head(o):
    co = verts(o); x, y, z = co.T
    a = o.data.color_attributes["makeup"]
    rgba = np.empty(len(co) * 4, np.float32); a.data.foreach_get("color", rgba); rgba = rgba.reshape(-1, 4)
    for c, r in Hd.INFO.get("eyes", []):                         # navy harlequin marks through the eyes
        dia = np.abs(x - c.x) / 0.011 + np.abs(z - c.z) / 0.060
        m = (dia < 1.0) & (y < c.y + 0.02) & (np.abs(z - c.z) > 0.012)
        rgba[m, :3] = NAVY * 1.4
    skull = (x / 0.114) ** 2 + ((y - 0.03) / 0.126) ** 2 + ((z - 1.80) / 0.152) ** 2
    hairm = (skull > 1.15) & (np.abs(x) > 0.09) & (z > 1.74)
    rgba[hairm, :3] = np.array([0.40, 0.02, 0.02]); rgba[hairm, 3] = 0
    a.data.foreach_set("color", rgba.ravel())


def socks(o):
    co = verts(o)
    a = o.data.color_attributes["makeup"]
    rgba = np.empty(len(co) * 4, np.float32); a.data.foreach_get("color", rgba); rgba = rgba.reshape(-1, 4)
    sock = co[:, 2] < 0.32
    band = np.sin(co[:, 2] * 2 * np.pi / 0.032) > 0
    rgba[sock & band, :3] = np.array([0.40, 0.025, 0.02]); rgba[sock & ~band, :3] = np.array([0.70, 0.64, 0.55])
    rgba[sock, 3] = 0
    a.data.foreach_set("color", rgba.ravel())


def blood_v4(top, pants, ruff_o, boots_o, pompoms_o):
    co = verts(top); front = (co[:, 1] < -0.02).astype(float)
    drips = [(rng.uniform(-0.15, 0.15), 1.58 - abs(rng.normal(0, 0.02)), rng.uniform(0.10, 0.45), rng.uniform(0.004, 0.012)) for _ in range(18)]
    b = C3.streaks(co, drips, front, wob=0.006)
    b = np.maximum(b, C3.spatter(co, (0.0, -0.25, 1.25), (0.18, 0.03, 0.18), 140, 0.002, 0.012, front))
    b = np.maximum(b, C3.spatter(co, (0.0, -0.25, 1.15), (0.10, 0.03, 0.06), 12, 0.02, 0.05, front) * 0.8)
    for sx in (1, -1):
        s, e, w, d = A.arm_points(sx)
        b = np.maximum(b, np.clip((0.12 - np.linalg.norm(co - np.array(w - d * 0.08), axis=1)) / 0.05, 0, 1) * 0.85)
    C3.set_attr(top, "blood", b)
    co = verts(pants); front = (co[:, 1] < 0.0).astype(float)
    b = C3.spatter(co, (0.0, -0.25, 0.70), (0.18, 0.03, 0.25), 140, 0.003, 0.014, front)
    b = np.maximum(b, C3.spatter(co, (0.0, -0.22, 0.80), (0.14, 0.03, 0.20), 10, 0.02, 0.05, front) * 0.8)
    C3.set_attr(pants, "blood", b)
    co = verts(ruff_o)
    C3.set_attr(ruff_o, "blood", np.clip((0.0 - co[:, 1]) / 0.08, 0, 1) * (0.5 + 0.5 * np.sin(co[:, 0] * 80) ** 2))
    for o in boots_o:
        co = verts(o); C3.set_attr(o, "blood", C3.spatter(co, (co[:, 0].mean(), -0.2, 0.08), (0.06, 0.12, 0.05), 40, 0.003, 0.012, 1.0))
    for o in pompoms_o:
        co = verts(o); C3.set_attr(o, "blood", 0.4 * (np.sin(co[:, 0] * 300) > 0.6))


# ================================================================== materials
def fabric_mat(name, rough, sheen):
    m, nt, b = B.nodes_mat(name)
    at = nt.nodes.new("ShaderNodeVertexColor"); at.layer_name = "fabric"
    tc = nt.nodes.new("ShaderNodeTexCoord")
    dirt = B.N(nt, "ShaderNodeTexNoise", Scale=5.0, Detail=10.0, Roughness=0.7); B.L(nt, tc.outputs["Object"], dirt.inputs["Vector"])
    dr = B.ramp(nt, [(0.40, (1, 1, 1)), (0.78, (0.35, 0.28, 0.20))]); B.L(nt, dirt.outputs["Fac"], dr.inputs["Fac"])
    grime = B.N(nt, "ShaderNodeTexNoise", Scale=40.0, Detail=6.0); B.L(nt, tc.outputs["Object"], grime.inputs["Vector"])
    gr = B.ramp(nt, [(0.35, (1, 1, 1)), (0.70, (0.72, 0.66, 0.58))]); B.L(nt, grime.outputs["Fac"], gr.inputs["Fac"])
    m1 = B.N(nt, "ShaderNodeMix", _data_type='RGBA', _blend_type='MULTIPLY', Factor=1.0)
    B.L(nt, at.outputs["Color"], m1.inputs[6]); B.L(nt, dr.outputs["Color"], m1.inputs[7])
    m2 = B.N(nt, "ShaderNodeMix", _data_type='RGBA', _blend_type='MULTIPLY', Factor=1.0)
    B.L(nt, m1.outputs[2], m2.inputs[6]); B.L(nt, gr.outputs["Color"], m2.inputs[7])
    B.L(nt, m2.outputs[2], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = rough; b.inputs["Sheen Weight"].default_value = sheen
    weave = B.N(nt, "ShaderNodeTexNoise", Scale=1500.0, Detail=1.0); B.L(nt, tc.outputs["Object"], weave.inputs["Vector"])
    bump = B.N(nt, "ShaderNodeBump", Strength=0.2, Distance=0.0004); B.L(nt, weave.outputs["Fac"], bump.inputs["Height"]); B.L(nt, bump.outputs[0], b.inputs["Normal"])
    return C3.add_blood(m)


def materials():
    mats = C3.materials()
    mats["fabric"] = fabric_mat("Fabric", 0.85, 0.45)
    mats["leather"] = fabric_mat("Leather", 0.42, 0.0)
    mats["hair"] = C3.add_blood(B.mat_simple("Hair_Red", (0.24, 0.008, 0.008), 0.62, **{"Sheen Weight": 0.3}))
    mats["wood"] = C3.add_blood(B.mat_simple("Axe_Wood", (0.22, 0.12, 0.05), 0.7))
    mats["steel"] = C3.add_blood(B.mat_simple("Axe_Steel", (0.45, 0.45, 0.47), 0.35, **{"Metallic": 1.0}))
    return mats


def build_high():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    mats = materials()
    cb = B.new_coll("Body"); cc = B.new_coll("Costume")
    body, F = C3.build_body(cb, mats); socks(body)
    head, eyes = C3.build_head(cb, mats); repaint_head(head)
    BR.face_parts.__globals__["A"] = A
    for o in BR.face_parts(cb, mats):
        if o.name != "Nails":
            bpy.data.objects.remove(o)
    for i, e in enumerate(eyes):
        e.name = f"Eye_{'LR'[i]}"
    top, S = puff_top(F, cc, mats)
    pants, P = bloomers(F, cc, mats)
    r = ruff(cc, mats); cf = cuffs(cc, mats); bt = boots(cc, mats); pp = pompoms(S, cc, mats)
    hair(cb, mats); axe(cc, mats)
    blood_v4(top, pants, r, bt, pp)
    for o in bpy.data.objects:                          # every mesh carries both attributes so baking is uniform
        if o.type == 'MESH':
            if "blood" not in o.data.color_attributes:
                C3.set_attr(o, "blood", np.zeros(len(o.data.vertices)))
    return mats


if __name__ == "__main__" and MODE == "preview":
    os.makedirs(OUT, exist_ok=True)
    build_high()
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "preview_high.blend"), compress=True)
    for o in bpy.data.objects:
        if o.type == 'MESH':
            print("MESH", o.name, sum(len(p.vertices) - 2 for p in o.data.polygons))


# ================================================================== game mesh, two skins, Unity sets
LOD = {  # name: (triangle budget, texture size)
    "Head": (60000, 2048), "Body": (30000, 2048), "Top": (32000, 2048), "Pants": (30000, 2048),
    "Ruff": (16000, 1024), "Cuff_L": (3000, 512), "Cuff_R": (3000, 512), "Boot_L": (6000, 1024), "Boot_R": (6000, 1024),
    "Hair": (12000, 1024), "Pompom_0": (1500, 256), "Pompom_1": (1500, 256), "Pompom_2": (1500, 256),
    "Eye_L": (None, 256), "Eye_R": (None, 256), "Nails": (None, 256), "Axe_Handle": (None, 512), "Axe_Head": (None, 512),
}
METALLIC = {"Axe_Head": 1.0}


def blood_amount(v):
    for m in bpy.data.materials:
        if m.node_tree and "BloodAmount" in m.node_tree.nodes:
            m.node_tree.nodes["BloodAmount"].inputs[1].default_value = v


def bake_all(hi, lo, size, tex):
    sc = bpy.context.scene
    base = lo.name.replace("_LOD0", "")
    names = ["BaseColor", "BaseColor_Clean", "Roughness", "Roughness_Clean", "Normal", "AO"]
    imgs = {k: bpy.data.images.new(f"{base}_{k}", size, size) for k in names}
    for k in ("Roughness", "Roughness_Clean", "Normal", "AO"):
        imgs[k].colorspace_settings.name = 'Non-Color'
    m, nt, b = B.nodes_mat(base + "_Game")
    nodes = {k: nt.nodes.new("ShaderNodeTexImage") for k in names}
    for k, n in nodes.items():
        n.image = imgs[k]
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nt.links.new(nodes["BaseColor"].outputs[0], b.inputs["Base Color"])
    nt.links.new(nodes["Roughness"].outputs[0], b.inputs["Roughness"])
    nt.links.new(nodes["Normal"].outputs[0], nm.inputs["Color"]); nt.links.new(nm.outputs[0], b.inputs["Normal"])
    b.inputs["Metallic"].default_value = METALLIC.get(base, 0.0)
    hb = [n for n in hi.active_material.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'][0]
    for k in ("Coat Weight", "Subsurface Weight", "Sheen Weight", "Emission Strength"):
        if not hb.inputs[k].is_linked:
            b.inputs[k].default_value = hb.inputs[k].default_value
    b.inputs["Emission Color"].default_value = hb.inputs["Emission Color"].default_value
    lo.data.materials.append(m)
    BR.only([hi, lo], active=lo)
    bk = sc.render.bake
    bk.use_selected_to_active = True; bk.cage_extrusion = 0.008; bk.max_ray_distance = 0.02; bk.margin = 6
    bk.use_pass_direct = False; bk.use_pass_indirect = False; bk.use_pass_color = True
    for k, kind, blood in (("BaseColor", 'DIFFUSE', 1.0), ("Roughness", 'ROUGHNESS', 1.0),
                           ("BaseColor_Clean", 'DIFFUSE', 0.0), ("Roughness_Clean", 'ROUGHNESS', 0.0),
                           ("Normal", 'NORMAL', 1.0), ("AO", 'AO', 1.0)):
        blood_amount(blood)
        nt.nodes.active = nodes[k]
        if kind == 'AO':
            sc.cycles.samples = 32
        bpy.ops.object.bake(type=kind)
        sc.cycles.samples = 1
        imgs[k].filepath_raw = os.path.join(tex, imgs[k].name + ".png"); imgs[k].file_format = 'PNG'; imgs[k].save()
    blood_amount(1.0)


def unity_pack(tex, parts):
    """Built-in/URP: Albedo, Normal, MetallicSmoothness (A = smoothness), Occlusion. HDRP: MaskMap (R metal, G AO, B detail, A smooth)."""
    from PIL import Image
    for p in parts:
        rough = np.asarray(Image.open(os.path.join(tex, f"{p}_Roughness.png")).convert("L"), np.float32) / 255
        rough_c = np.asarray(Image.open(os.path.join(tex, f"{p}_Roughness_Clean.png")).convert("L"), np.float32) / 255
        ao = np.asarray(Image.open(os.path.join(tex, f"{p}_AO.png")).convert("L"), np.float32) / 255
        met = np.full_like(rough, METALLIC.get(p, 0.0))
        for suffix, r in (("", rough), ("_Clean", rough_c)):
            sm = 1 - r
            ms = np.stack([met, met, met, sm], -1)
            Image.fromarray((ms * 255).astype(np.uint8), "RGBA").save(os.path.join(tex, f"{p}_MetallicSmoothness{suffix}.png"))
            mk = np.stack([met, ao, np.ones_like(ao), sm], -1)
            Image.fromarray((mk * 255).astype(np.uint8), "RGBA").save(os.path.join(tex, f"{p}_MaskMap{suffix}.png"))
        os.replace(os.path.join(tex, f"{p}_AO.png"), os.path.join(tex, f"{p}_Occlusion.png"))


def pose_menace(rig):
    """As in the concept: weight forward, head cocked, arms out at the sides with clawed hands, knees soft."""
    BR.only([rig]); bpy.ops.object.mode_set(mode='POSE')
    pb = rig.pose.bones

    def turn(name, axis, deg, local=False):
        b = pb[name]; bpy.context.view_layer.update()
        ax = (b.matrix.to_3x3() @ Vector((1, 0, 0))).normalized() if local else Vector({'X': (1, 0, 0), 'Y': (0, 1, 0), 'Z': (0, 0, 1)}[axis])
        h = b.head.copy()
        b.matrix = Matrix.Translation(h) @ Matrix.Rotation(math.radians(deg), 4, ax) @ Matrix.Translation(-h) @ b.matrix
        bpy.context.view_layer.update()
    turn("Spine1", 'X', 5); turn("Neck", 'X', 4); turn("Head", 'X', 9); turn("Head", 'Y', 9)
    for side, sx in (("Left", 1), ("Right", -1)):
        turn(side + "ForeArm", 'X', 16)
        for f in ("Index", "Middle", "Ring", "Pinky"):
            for k in (1, 2, 3):
                turn(f"{side}Hand{f}{k}", 'X', 22 if side == "Left" else 34, local=True)
        turn(side + "UpLeg", 'X', -6); turn(side + "Leg", 'X', 11)
    bpy.ops.object.mode_set(mode='OBJECT')


def full():
    tex = os.path.join(OUT, "Textures"); os.makedirs(tex, exist_ok=True)
    build_high()
    sc = bpy.context.scene; sc.render.engine = 'CYCLES'; sc.cycles.samples = 1; sc.cycles.device = 'CPU'
    for c in ("Body", "Costume"):
        bpy.data.collections[c].name = c + "_HighPoly"
    game = B.new_coll("Game_LOD0"); lows = {}
    for name, (budget, size) in LOD.items():
        hi = bpy.data.objects[name]
        lo = C3.make_lod(hi, budget, game)
        bake_all(hi, lo, size, tex)
        lows[name] = lo
        print(f"LOD {name}: {BR.tris(hi)} -> {BR.tris(lo)} tris", flush=True)
    unity_pack(tex, list(LOD))
    BR.only([lows["Head"], lows["Body"]], active=lows["Body"]); bpy.ops.object.join()
    body = lows.pop("Body"); lows.pop("Head"); body.name = "Clown_Body"
    rig = BR.skeleton(game); rig.name = "Clown_Rig"
    BR.only([body, rig], active=rig); bpy.ops.object.parent_set(type='ARMATURE_AUTO')
    weapon = [lows.pop("Axe_Handle"), lows.pop("Axe_Head")]
    for n, o in lows.items():
        if n.startswith(("Eye", "Hair")):
            vg = o.vertex_groups.new(name="Head"); vg.add(list(range(len(o.data.vertices))), 1.0, 'REPLACE')
        else:
            for g in body.vertex_groups:
                o.vertex_groups.new(name=g.name)
            dt = o.modifiers.new("w", 'DATA_TRANSFER'); dt.object = body
            dt.use_vert_data = True; dt.data_types_verts = {'VGROUP_WEIGHTS'}; dt.vert_mapping = 'POLYINTERP_NEAREST'
            BR.only([o]); bpy.ops.object.datalayout_transfer(modifier="w"); bpy.ops.object.modifier_apply(modifier="w")
        o.parent = rig; o.modifiers.new("Armature", 'ARMATURE').object = rig
        o.name = n
    BR.only([weapon[1], weapon[0]], active=weapon[0]); bpy.ops.object.join(); ax = weapon[0]; ax.name = "Axe"
    mw = ax.matrix_world.copy()
    ax.parent = rig; ax.parent_type = 'BONE'; ax.parent_bone = "RightHand"; ax.matrix_world = mw
    allm = [body] + list(lows.values()) + [ax]
    total = sum(BR.tris(o) for o in allm)
    print("TOTAL TRIS", total, "VERTS", sum(len(o.data.vertices) for o in allm), "AXE", BR.tris(ax), len(ax.data.vertices), flush=True)
    BR.only(allm + [rig], active=rig)
    bpy.ops.export_scene.fbx(filepath=os.path.join(OUT, "Clown.fbx"), use_selection=True, add_leaf_bones=False,
                             path_mode='STRIP', embed_textures=False, axis_forward='-Z', axis_up='Y', apply_unit_scale=True)
    bpy.ops.export_scene.gltf(filepath=os.path.join(OUT, "Clown.glb"), use_selection=True, export_format='GLB',
                              export_skins=True, export_animations=False)
    for c in ("Body", "Costume"):
        col = bpy.data.collections[c + "_HighPoly"]
        for o in list(col.objects):
            bpy.data.objects.remove(o)
        bpy.data.collections.remove(col)
    bpy.ops.outliner.orphans_purge(do_recursive=True) if bpy.context.area else None
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "Clown.blend"), compress=True)
    pose_menace(rig)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "Clown_posed.blend"), compress=True, copy=True)
    return total


if __name__ == "__main__" and MODE in ("full", "fullquick"):
    os.makedirs(OUT, exist_ok=True)
    print("DONE", full())
