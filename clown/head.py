"""Head built from the client's reference sculpt (a clown mask): the mask surface becomes a signed
distance field, a skull core fills it from behind, eye holes become sockets, and the neck matches
the body's. Sampled finer than the body so the reference wrinkles survive."""
import math
import numpy as np
import bpy
from mathutils import Vector
from scipy.spatial import cKDTree
from scipy import ndimage
from sdf import Field

S = 0.1087                         # reference units -> metres (chin to crown ~0.30 m)
T = np.array([0.0, -0.020, 1.768])  # chin lands at z = 1.655
INFO = {}


def load_mask(path):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=path)
    o = [x for x in bpy.data.objects if x not in before and x.type == 'MESH'][0]
    deps = bpy.context.evaluated_depsgraph_get()
    me = o.evaluated_get(deps).to_mesh()
    M = np.array(o.matrix_world)
    n = len(me.vertices)
    co = np.empty(n * 3, np.float32); me.vertices.foreach_get("co", co); co = co.reshape(-1, 3)
    nr = np.empty(n * 3, np.float32); me.vertices.foreach_get("normal", nr); nr = nr.reshape(-1, 3)
    co = co @ M[:3, :3].T + M[:3, 3]
    R = M[:3, :3] / np.linalg.norm(M[:3, :3], axis=0)
    nr = nr @ R.T; nr /= np.linalg.norm(nr, axis=1, keepdims=True) + 1e-9
    for ob in [x for x in bpy.data.objects if x not in before]:
        bpy.data.objects.remove(ob)
    return co * S + T, nr


def head_field(mask_path, h=0.0009, neck_r=(0.096, 0.086)):
    pts, nrm = load_mask(mask_path)
    INFO["nose"] = Vector(pts[pts[:, 1].argmin()])
    INFO["chin"] = Vector(pts[pts[:, 2].argmin()])
    F = Field((-0.180, -0.200, 1.500), (0.180, 0.200, 1.985), h)
    nx, ny, nz = F.n
    xs = F.lo[0] + F.h * np.arange(nx); ys = F.lo[1] + F.h * np.arange(ny); zs = F.lo[2] + F.h * np.arange(nz)
    tree = cKDTree(pts)
    D = np.full((nx, ny, nz), 0.05, np.float32)
    half = 0.0028                                         # half the shell thickness, metres
    for i in range(nx):                                   # slab by slab to bound memory
        Y, Z = np.meshgrid(ys, zs, indexing="ij")
        P = np.stack([np.full(Y.size, xs[i]), Y.ravel(), Z.ravel()], 1)
        d, j = tree.query(P, distance_upper_bound=0.006, workers=-1)
        ok = np.isfinite(d)
        sgn = np.ones(len(P), np.float32)
        sgn[ok] = np.sign(np.einsum("ij,ij->i", P[ok] - pts[j[ok]], nrm[j[ok]]))
        inside = ok & (sgn < 0) & (d < half)
        val = np.where(ok, d, 0.006).astype(np.float32)
        val[inside] = -d[inside]
        D[i] = val.reshape(ny, nz)
    shell = D < 0
    # fill the hollow behind the mask: everything between the first and last shell voxel of a column
    a = np.maximum.accumulate(shell, axis=1)
    b = np.maximum.accumulate(shell[:, ::-1], axis=1)[:, ::-1]
    D[a & b & ~shell] = -0.0015
    # first hit of the face plate (front half of the mask) for every (x, z) column
    jfront = int((-0.03 - F.lo[1]) / F.h)
    plate = shell.copy(); plate[:, jfront:, :] = False
    has = plate.any(axis=1)
    first = np.argmax(plate, axis=1).astype(np.float32)
    yf = np.where(has, F.lo[1] + F.h * first, np.nan)
    # holes inside the face (eyes): filled silhouette minus actual coverage
    filled = ndimage.binary_fill_holes(has)
    holes = filled & ~has
    idx = ndimage.distance_transform_edt(~has, return_distances=False, return_indices=True)
    yfill = yf[idx[0], idx[1]]
    clip = np.where(has, yf + 0.0035, np.where(holes, yfill + 0.016, np.nan))
    # eye sockets: the two largest holes at eye height
    lab, nlab = ndimage.label(holes)
    eyes = []
    for k in range(1, nlab + 1):
        cells = np.argwhere(lab == k)
        if len(cells) < 40:
            continue
        cx = F.lo[0] + F.h * cells[:, 0].mean(); cz = F.lo[2] + F.h * cells[:, 1].mean()
        if abs(cz - 1.818) < 0.03 and 0.015 < abs(cx) < 0.07:
            w = F.h * (cells[:, 0].max() - cells[:, 0].min()); hh = F.h * (cells[:, 1].max() - cells[:, 1].min())
            yb = np.nanmean(yfill[cells[:, 0], cells[:, 1]])
            eyes.append((len(cells), Vector((cx, yb + 0.011, cz)), min(w, hh) * 0.62))
    eyes.sort(key=lambda e: -e[0])
    r_eye = min(r for _, _, r in eyes[:2]) * 1.08 if eyes else 0.016
    INFO["eyes"] = [(c, r_eye) for _, c, r in eyes[:2]]
    F.D = D
    # skull core + neck, kept behind the mask's front surface
    core = Field(tuple(F.lo), tuple(F.lo + F.h * (F.n - 1)), F.h)
    core.n = F.n.copy(); core.D = np.full(tuple(F.n), 0.05, np.float32)
    core.ell((0, 0.030, 1.805), (0.091, 0.110, 0.132), k=0.05)      # skull
    core.ell((0, 0.060, 1.760), (0.090, 0.085, 0.110), k=0.06)      # occiput, heavy
    core.ell((0, 0.000, 1.705), (0.092, 0.075, 0.060), k=0.06)      # jaw and jowls into the neck
    core.cap((0, 0.020, 1.500), (0, 0.010, 1.700), *neck_r, k=0.07)
    Yg = (F.lo[1] + F.h * np.arange(ny))[None, :, None]
    lim = np.where(np.isnan(clip), -1.0, clip)[:, None, :]
    behind = (lim - Yg).astype(np.float32)                         # > 0 in front of the limit
    core.D = np.maximum(core.D, np.where(np.isnan(clip)[:, None, :], -1.0, behind))
    hh = np.clip(0.5 + 0.5 * (F.D - core.D) / 0.004, 0, 1)
    F.D = (F.D * (1 - hh) + core.D * hh - 0.004 * hh * (1 - hh)).astype(np.float32)
    # soften seams: a whisper of blur on the face, a stronger one behind the mask rim
    fine = ndimage.gaussian_filter(F.D, 0.9)
    soft = ndimage.gaussian_filter(F.D, 0.0035 / F.h)
    w = np.clip((Yg - 0.0) / 0.04, 0, 1)
    rim = ndimage.binary_dilation(has, iterations=int(0.006 / F.h)) & ~ndimage.binary_erosion(has, iterations=int(0.004 / F.h))
    rim = ndimage.gaussian_filter(rim.astype(np.float32), 0.003 / F.h)[:, None, :]
    w = np.maximum(w, np.clip(rim * 1.6, 0, 0.9))
    F.D = (fine * (1 - w) + soft * w).astype(np.float32)
    return F


def paint_head(o, blood_attr=True):
    me = o.data; n = len(me.vertices)
    co = np.empty(n * 3, np.float32); me.vertices.foreach_get("co", co); co = co.reshape(-1, 3)
    x, y, z = co[:, 0], co[:, 1], co[:, 2]
    rng = np.random.default_rng(3)
    white = np.array([0.86, 0.85, 0.80]); skin = np.array([0.52, 0.45, 0.40])
    col = np.tile(white, (n, 1)); paint = np.ones(n)
    neckw = np.clip((z - 1.60) / 0.06, 0, 1)
    col = col * neckw[:, None] + skin * (1 - neckw[:, None]); paint *= neckw
    nose = INFO["nose"]
    dn = np.linalg.norm(co - np.array(nose) - np.array([0, 0.03, 0]), axis=1)
    m = np.clip((0.040 - dn) / 0.004, 0, 1) * (y < nose.y + 0.05)
    col = col * (1 - m[:, None]) + np.array([0.42, 0.02, 0.02]) * m[:, None]
    # sooty eye sockets with tear streaks
    for c, r in INFO.get("eyes", []):
        e = np.sqrt(((x - c.x) / 0.036) ** 2 + ((z - c.z) / 0.030) ** 2)
        mm = np.clip((1 - e) / 0.3, 0, 1) * (y < c.y + 0.02)
        col = col * (1 - mm[:, None]) + np.array([0.03, 0.025, 0.03]) * mm[:, None]
    # mouth: teeth inside, red lips around
    mz = 1.719
    e = np.sqrt((x / 0.064) ** 2 + ((z - mz) / 0.026) ** 2)
    front = y < -0.06
    teeth = (e < 1.0) & front
    lips = (e >= 1.0) & (e < 1.42) & front
    col[teeth] = np.array([0.80, 0.74, 0.58]) * (0.85 + 0.15 * rng.random((teeth.sum(), 1)))
    col[lips] = np.array([0.30, 0.012, 0.016])
    # hair tufts: geometry far outside the skull at the temples
    skull = (x / 0.114) ** 2 + ((y - 0.03) / 0.126) ** 2 + ((z - 1.80) / 0.152) ** 2
    hair = (skull > 1.22) & (np.abs(x) > 0.10) & (z > 1.75) & (y > -0.10)
    col[hair] = np.array([0.34, 0.06, 0.02]); paint[hair] = 0
    a = me.color_attributes.new("makeup", 'FLOAT_COLOR', 'POINT')
    a.data.foreach_set("color", np.concatenate([col, paint[:, None]], 1).astype(np.float32).ravel())
    # blood: drooling from the mouth corners and teeth, tears of blood from the eyes
    blood = np.zeros(n)
    for k in range(14):
        sx = rng.uniform(-0.055, 0.055); top = mz - 0.012 + 0.4 * abs(sx) ** 2 * 10
        L = rng.uniform(0.02, 0.07); w = rng.uniform(0.0015, 0.004)
        streak = np.clip(1 - np.abs(x - sx - 0.15 * (top - z) * np.sign(sx) * 0.2) / w, 0, 1) * (z < top) * (z > top - L) * front
        tip = np.clip(1 - np.linalg.norm(np.stack([x - sx, (z - (top - L)) * 1.4], 1), axis=1) / (w * 1.8), 0, 1) * front
        blood = np.maximum(blood, np.maximum(streak, tip))
    gum = np.clip(1 - np.abs(e - 1.0) / 0.12, 0, 1)                       # blood along the gum line
    blood = np.maximum(blood, gum * front * 0.8)
    blood = np.maximum(blood, teeth * 0.25 * (np.sin(x * 260) > 0.3))
    for c, r in INFO.get("eyes", []):
        for dx in (-0.006, 0.004):
            st = np.clip(1 - np.abs(x - c.x - dx) / 0.0022, 0, 1) * (z < c.z - 0.008) * (z > c.z - 0.06) * (y < c.y)
            blood = np.maximum(blood, st)
    b = me.color_attributes.new("blood", 'FLOAT_COLOR', 'POINT')
    b.data.foreach_set("color", np.repeat(blood[:, None], 4, 1).astype(np.float32).ravel())
