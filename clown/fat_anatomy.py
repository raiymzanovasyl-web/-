"""Heavy-set body for the clown: soft fat over muscle, round belly that overhangs,
thick neck, full arms and legs. Metres, Z up, facing -Y. The head comes from head.py."""
import math
from mathutils import Vector, Quaternion
from sdf import Field

NAILS, JOINTS = [], {}
EYES = []          # the head module places the eyes


def mirror(fn):
    for sx in (1, -1):
        fn(sx)


def rotate_toward(d, toward, deg):
    axis = d.cross(toward)
    if axis.length < 1e-6:
        return d.copy()
    return (Quaternion(axis.normalized(), math.radians(deg)) @ d).normalized()


SHOULDER = (0.265, 0.010, 1.520)
ARM_DOWN = 52.0
UPPER, FORE = 0.320, 0.285
HIP, KNEE, ANKLE = (0.125, 0.020, 0.930), (0.140, -0.005, 0.510), (0.150, 0.025, 0.095)
FINGERS = [(-0.029, 0.088), (-0.010, 0.098), (0.009, 0.094), (0.027, 0.078)]


def arm_points(sx):
    s = Vector((SHOULDER[0] * sx, SHOULDER[1], SHOULDER[2]))
    a = math.radians(ARM_DOWN)
    d = Vector((sx * math.cos(a), 0.0, -math.sin(a))).normalized()
    e = s + d * UPPER
    return s, e, e + d * FORE, d


def hand_frame(sx, d):
    inward = Vector((-sx * math.sin(math.radians(ARM_DOWN)), 0, -math.cos(math.radians(ARM_DOWN))))
    inward = (inward - d * inward.dot(d)).normalized()
    across = d.cross(inward).normalized()
    if across.y > 0:
        across = -across
    return inward, across


def neck(F):
    F.cap((0, 0.020, 1.500), (0, 0.010, 1.700), 0.096, 0.086, k=0.07)
    mirror(lambda sx: F.ell((sx * 0.120, 0.045, 1.590), (0.120, 0.070, 0.055), rot=(0, sx * 22, 0), k=0.08))   # trapezius under fat


def torso(F):
    F.ell((0, 0.015, 1.405), (0.200, 0.150, 0.190), k=0.09)            # rib cage + fat
    F.ell((0, 0.020, 1.530), (0.245, 0.120, 0.075), k=0.09)            # shoulder girdle
    F.ell((0, -0.060, 1.185), (0.215, 0.205, 0.195), k=0.10)           # round belly
    F.ell((0, -0.085, 1.085), (0.175, 0.165, 0.095), k=0.09)           # belly overhang
    F.ell((0, 0.030, 1.000), (0.205, 0.145, 0.110), k=0.09)            # pelvis
    F.ell((0, -0.262, 1.160), (0.010, 0.010, 0.016), k=0.010, neg=True)  # navel
    F.ell((0, -0.155, 1.400), (0.016, 0.016, 0.060), k=0.04, neg=True)   # soft sternum valley

    def side(sx):
        F.ell((sx * 0.105, -0.115, 1.435), (0.098, 0.050, 0.080), rot=(0, sx * -10, 0), k=0.05)   # heavy chest
        F.ell((sx * 0.115, -0.130, 1.372), (0.070, 0.030, 0.022), rot=(0, sx * -8, 0), k=0.04)    # chest sag
        F.ell((sx * 0.180, 0.050, 1.385), (0.055, 0.085, 0.150), rot=(0, sx * 8, 0), k=0.08)      # back / lats
        F.ell((sx * 0.200, -0.010, 1.130), (0.060, 0.125, 0.085), k=0.08)                         # love handle
        F.ell((sx * 0.140, 0.120, 1.215), (0.070, 0.035, 0.040), k=0.06)                          # back fat roll
        F.ell((sx * 0.100, 0.115, 0.965), (0.100, 0.080, 0.105), k=0.07)                          # gluteus
        F.ell((sx * 0.050, 0.130, 1.300), (0.040, 0.025, 0.150), k=0.06)                          # spine muscles
    mirror(side)


def arms(F):
    def side(sx):
        s, e, w, d = arm_points(sx)
        F.cap(s, e, 0.074, 0.060, k=0.07)
        F.cap(e, w, 0.058, 0.040, k=0.05)
        F.along(s + Vector((0, 0, 0.02)), e, 0.110, 0.078, 0.074, at=0.12, k=0.07)           # deltoid
        F.along(s, e, 0.120, 0.058, 0.055, offset=(0, 0.018, -0.006), at=0.50, k=0.06)       # soft upper arm
        F.along(e, w, 0.100, 0.044, 0.040, offset=(0, -0.006, 0), at=0.26, k=0.05)           # forearm mass
        F.ell(w, (0.030, 0.040, 0.020), rot=Vector((1, 0, 0)).rotation_difference(d), k=0.03)
        hand(F, sx, w, d)
    mirror(side)


def hand(F, sx, w, d):
    inward, across = hand_frame(sx, d)
    q = Vector((1, 0, 0)).rotation_difference(d)
    F.ell(w + d * 0.056, (0.058, 0.052, 0.024), rot=q, k=0.022)
    F.ell(w + d * 0.040 - across * 0.032 + inward * 0.012, (0.034, 0.020, 0.020), rot=q, k=0.02)
    for fi, (off, length) in enumerate(FINGERS):
        base = w + d * 0.106 + across * off * 1.55
        JOINTS[(sx, fi + 1)] = [base.copy()]
        F.ell(base - inward * 0.004, (0.0160,) * 3, k=0.012)
        dirn = rotate_toward(d, across, off * 90); p = base
        for i, L in enumerate((length * 0.44, length * 0.32, length * 0.24)):
            dirn = rotate_toward(dirn, inward, (12, 20, 18)[i])
            q2 = p + dirn * L
            r = (0.0145, 0.0130, 0.0115)[i]
            F.cap(p, q2, r, r * 0.92, k=0.007)
            p = q2
            JOINTS[(sx, fi + 1)].append(p.copy())
        NAILS.append((p.copy(), dirn.copy(), inward.copy(), 0.010))
    base = w + d * 0.035 - across * 0.044 + inward * 0.016
    dirn = rotate_toward(rotate_toward(d, across, -50), inward, 25); p = base
    JOINTS[(sx, 0)] = [base.copy()]
    for i, L in enumerate((0.048, 0.040, 0.032)):
        dirn = rotate_toward(dirn, inward, 12)
        q2 = p + dirn * L
        r = (0.019, 0.016, 0.014)[i]
        F.cap(p, q2, r, r * 0.9, k=0.014 if i else 0.022)
        p = q2
        JOINTS[(sx, 0)].append(p.copy())
    NAILS.append((p.copy(), dirn.copy(), inward.copy(), 0.012))


def legs(F):
    def side(sx):
        h = Vector((HIP[0] * sx, HIP[1], HIP[2])); kn = Vector((KNEE[0] * sx, KNEE[1], KNEE[2]))
        a = Vector((ANKLE[0] * sx, ANKLE[1], ANKLE[2]))
        F.cap(h, kn, 0.128, 0.084, k=0.08)
        F.cap(kn, a, 0.082, 0.050, k=0.06)
        F.along(h, kn, 0.160, 0.060, 0.055, offset=(sx * 0.010, -0.025, 0), at=0.45, k=0.06)   # thigh mass
        F.along(h, kn, 0.120, 0.050, 0.050, offset=(sx * -0.040, 0.0, 0), at=0.30, k=0.06)     # inner thigh
        F.ell(kn + Vector((0, -0.070, 0.004)), (0.030, 0.016, 0.032), k=0.03)                  # knee
        F.along(kn, a, 0.120, 0.058, 0.058, offset=(0, 0.035, 0), at=0.28, k=0.05)            # calf
        F.ell(a + Vector((0, 0.040, -0.052)), (0.038, 0.042, 0.042), k=0.03)                  # heel
        F.ell(a + Vector((0, -0.075, -0.070)), (0.058, 0.115, 0.030), k=0.04)                 # foot
    mirror(side)


def body_field(h=0.0021):
    NAILS.clear(); JOINTS.clear()
    F = Field((-0.92, -0.36, -0.01), (0.92, 0.27, 1.76), h)
    torso(F); neck(F); arms(F); legs(F)
    return F
