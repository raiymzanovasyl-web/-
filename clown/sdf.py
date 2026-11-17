"""Tiny signed-distance sculpting kit: shapes are blended into a voxel field
with smooth union / smooth subtraction, then meshed with marching cubes."""
import math
import numpy as np
from mathutils import Vector, Quaternion, Euler


def _rot(rot):
    if rot is None:
        return np.eye(3, dtype=np.float32)
    if not isinstance(rot, Quaternion):
        rot = Euler([math.radians(v) for v in rot]).to_quaternion()
    return np.array(rot.to_matrix(), dtype=np.float32)


class Field:
    def __init__(self, lo, hi, h):
        self.lo = np.array(lo, np.float32)
        self.h = h
        self.n = (np.ceil((np.array(hi) - self.lo) / h).astype(int) + 1)
        self.D = np.full(tuple(self.n), 0.05, np.float32)

    def _region(self, bmin, bmax):
        i0 = np.clip(np.floor((np.array(bmin) - self.lo) / self.h).astype(int), 0, self.n - 1)
        i1 = np.clip(np.ceil((np.array(bmax) - self.lo) / self.h).astype(int) + 1, 0, self.n)
        if np.any(i1 <= i0):
            return None, None
        sl = tuple(slice(a, b) for a, b in zip(i0, i1))
        ax = [self.lo[k] + self.h * np.arange(i0[k], i1[k], dtype=np.float32) for k in range(3)]
        return sl, (ax[0][:, None, None], ax[1][None, :, None], ax[2][None, None, :])

    def _combine(self, d, sl, k, neg):
        D = self.D[sl]
        if neg:
            if k > 0:
                hh = np.clip(0.5 - 0.5 * (D + d) / k, 0, 1)
                D = D * (1 - hh) + (-d) * hh + k * hh * (1 - hh)
            else:
                D = np.maximum(D, -d)
        else:
            if k > 0:
                hh = np.clip(0.5 + 0.5 * (D - d) / k, 0, 1)
                D = D * (1 - hh) + d * hh - k * hh * (1 - hh)
            else:
                D = np.minimum(D, d)
        self.D[sl] = D

    # ---------------------------------------------------------------- shapes
    def ell(self, c, abc, rot=None, k=0.015, neg=False):
        c = np.array(c, np.float32); r = np.array(abc, np.float32)
        m = float(r.max()) + k + self.h * 2
        sl, (x, y, z) = self._region(c - m, c + m)
        if sl is None:
            return
        R = _rot(rot)
        px, py, pz = x - c[0], y - c[1], z - c[2]
        lx = R[0, 0] * px + R[1, 0] * py + R[2, 0] * pz
        ly = R[0, 1] * px + R[1, 1] * py + R[2, 1] * pz
        lz = R[0, 2] * px + R[1, 2] * py + R[2, 2] * pz
        k0 = np.sqrt((lx / r[0]) ** 2 + (ly / r[1]) ** 2 + (lz / r[2]) ** 2)
        k1 = np.sqrt((lx / r[0] ** 2) ** 2 + (ly / r[1] ** 2) ** 2 + (lz / r[2] ** 2) ** 2)
        d = k0 * (k0 - 1.0) / np.maximum(k1, 1e-6)
        self._combine(d.astype(np.float32), sl, k, neg)

    def cap(self, a, b, r0, r1=None, k=0.015, neg=False):
        r1 = r0 if r1 is None else r1
        a = np.array(a, np.float32); b = np.array(b, np.float32)
        m = max(r0, r1) + k + self.h * 2
        sl, (x, y, z) = self._region(np.minimum(a, b) - m, np.maximum(a, b) + m)
        if sl is None:
            return
        ba = b - a; L2 = float(ba @ ba)
        px, py, pz = x - a[0], y - a[1], z - a[2]
        t = np.clip((px * ba[0] + py * ba[1] + pz * ba[2]) / L2, 0, 1)
        dx, dy, dz = px - ba[0] * t, py - ba[1] * t, pz - ba[2] * t
        d = np.sqrt(dx * dx + dy * dy + dz * dz) - (r0 + (r1 - r0) * t)
        self._combine(d.astype(np.float32), sl, k, neg)

    def along(self, p0, p1, half_len, w, t, offset=(0, 0, 0), roll=0.0, at=0.5, k=0.015, neg=False):
        p0, p1 = Vector(p0), Vector(p1)
        d = (p1 - p0).normalized()
        q = Vector((1, 0, 0)).rotation_difference(d)
        if roll:
            q = Quaternion(d, math.radians(roll)) @ q
        self.ell(p0.lerp(p1, at) + Vector(offset), (half_len, w, t), rot=q, k=k, neg=neg)

    def mesh(self):
        from skimage.measure import marching_cubes
        v, f, _, _ = marching_cubes(self.D, level=0.0, spacing=(self.h,) * 3)
        return v + self.lo, f


def front_y(F, x, z, y0=-0.25, y1=0.1):
    """First y (scanning from the front) where the field is inside, at (x, z)."""
    i = int(round((x - F.lo[0]) / F.h)); k = int(round((z - F.lo[2]) / F.h))
    col = F.D[i, :, k]
    j0 = max(0, int((y0 - F.lo[1]) / F.h)); j1 = min(F.n[1] - 1, int((y1 - F.lo[1]) / F.h))
    for j in range(j0, j1):
        if col[j] <= 0:
            a, b = col[j - 1], col[j]
            return float(F.lo[1] + F.h * (j - 1 + a / (a - b)))
    return None
