"""The brute: a massive clown. Heavy trapezius, barrel chest, gut, thick limbs.
Head after the reference: bald dome, furrowed angry brow, fat cheeks and jowls, deep small eyes,
a wide snarl full of big square teeth. Metres, Z up, facing -Y."""
import math
from mathutils import Vector, Quaternion
from sdf import Field, front_y

EYES, NAILS, JOINTS = [], [], {}
MOUTH = {}      # 'upper'/'lower' teeth arcs and the gum line


def mirror(fn):
    for sx in (1, -1):
        fn(sx)


def rotate_toward(d, toward, deg):
    axis = d.cross(toward)
    if axis.length < 1e-6:
        return d.copy()
    return (Quaternion(axis.normalized(), math.radians(deg)) @ d).normalized()


# ---------------------------------------------------------------- head
HC = Vector((0, 0.0, 1.80))     # head reference point


def head(F):
    F.ell((0, 0.030, 1.850), (0.098, 0.112, 0.100), k=0.04)           # bald dome
    F.ell((0, -0.030, 1.770), (0.090, 0.085, 0.090), k=0.08)          # face mass
    F.ell((0, -0.072, 1.880), (0.084, 0.040, 0.052), rot=(-14, 0, 0), k=0.04)   # forehead
    F.ell((0, -0.040, 1.690), (0.078, 0.070, 0.045), k=0.05)          # heavy jaw
    F.ell((0, -0.092, 1.672), (0.040, 0.026, 0.028), k=0.035)         # chin

    def side(sx):
        F.ell((sx * 0.066, -0.060, 1.735), (0.046, 0.045, 0.048), k=0.04)            # jowl
        F.ell((sx * 0.052, -0.094, 1.770), (0.032, 0.026, 0.026), k=0.03)            # cheek apple pushed up
        F.ell((sx * 0.084, -0.008, 1.700), (0.026, 0.040, 0.034), k=0.04)            # masseter / jaw corner
        F.ell((sx * 0.036, -0.112, 1.808), (0.021, 0.022, 0.013), k=0.008, neg=True)  # deep-set orbit
        EYES.append((Vector((sx * 0.036, -0.1035, 1.809)), 0.0118))
        F.ell((sx * 0.038, -0.112, 1.792), (0.020, 0.010, 0.0075), rot=(10, 0, 0), k=0.008)   # bag
        F.ell((sx * 0.040, -0.114, 1.784), (0.018, 0.004, 0.0025), k=0.003, neg=True)          # bag crease
        # angry brow: low at the centre, rising outward, overhanging the eye
        F.cap((sx * 0.008, -0.126, 1.816), (sx * 0.080, -0.092, 1.862), 0.024, 0.016, k=0.020)
        F.ell((sx * 0.040, -0.111, 1.823), (0.024, 0.012, 0.006), rot=(0, sx * 28, 0), k=0.007)  # lid fold, angled like the brow
        F.ell((sx * 0.100, 0.004, 1.790), (0.012, 0.026, 0.036), rot=(0, sx * -10, 0), k=0.012)  # ear
        F.ell((sx * 0.104, 0.002, 1.792), (0.004, 0.015, 0.022), rot=(0, sx * -10, 0), k=0.004, neg=True)
        # nasolabial fold: a deep crease from the nose wing to the mouth corner
        F.along((sx * 0.026, -0.130, 1.762), (sx * 0.074, -0.098, 1.705), 0.036, 0.005, 0.005, k=0.008, neg=True)
    mirror(side)

    # glabella: a knot of muscle between the brows with vertical frown lines
    F.ell((0, -0.124, 1.836), (0.014, 0.010, 0.018), k=0.01)
    for sx in (1, -1):
        F.cap((sx * 0.006, -0.135, 1.826), (sx * 0.009, -0.133, 1.850), 0.0022, k=0.003, neg=True)
    # forehead wrinkles, snapped to the skin
    for row, z in enumerate((1.858, 1.874, 1.890)):
        pts = []
        for i in range(-9, 10):
            x = i * 0.0068 * (1 - 0.08 * row)
            zz = z + 0.004 * math.cos(i * 0.6 + row) - 0.010 * (abs(x) / 0.06) ** 2 * (1 if row < 2 else -0.5)
            y = front_y(F, x, zz, y0=-0.2, y1=0.0)
            if y is not None:
                pts.append(Vector((x, y + 0.0012, zz)))
        for a, b in zip(pts, pts[1:]):
            F.cap(a + Vector((0, 0.0015, 0)), b + Vector((0, 0.0015, 0)), 0.0022, k=0.004, neg=True)
            F.cap(a + Vector((0, 0.0010, 0.005)), b + Vector((0, 0.0010, 0.005)), 0.0030, k=0.008)

    # the snarl: wide, lips pulled back, upper lip hiked at the sides
    def mouth_z(x, upper):
        t = abs(x) / 0.074
        if upper:
            return 1.722 + 0.010 * (1 - t * t) - 0.006 * t ** 4 + 0.004 * math.sin(t * math.pi) ** 2
        return 1.692 - 0.008 * (1 - t * t) + 0.012 * t ** 3
    rim_u, rim_l = [], []
    for i in range(-14, 15):
        x = i * 0.0053
        for upper, arr in ((True, rim_u), (False, rim_l)):
            z = mouth_z(x, upper)
            y = front_y(F, x, z, y0=-0.2, y1=0.0)
            arr.append(Vector((x, (y if y is not None else -0.10) + 0.001, z)))
    # carve the opening between the rims, then roll thin lips onto the rims
    for a_, b_ in zip(rim_u, rim_l):
        F.cap(a_ + Vector((0, 0.002, -0.004)), b_ + Vector((0, 0.002, 0.004)), 0.0055, k=0.004, neg=True)
        F.cap(a_ + Vector((0, 0.022, -0.004)), b_ + Vector((0, 0.022, 0.004)), 0.0080, k=0.004, neg=True)
    F.ell((0, -0.070, 1.707), (0.066, 0.040, 0.024), k=0.006, neg=True)            # mouth cavity
    for arr, r in ((rim_u, 0.0060), (rim_l, 0.0072)):
        for a_, b_ in zip(arr, arr[1:]):
            F.cap(a_, b_, r, k=0.008)
    # teeth follow the opening, set just behind the lips
    def arc(arr, dz, count):
        out = []
        for j in range(count):
            f = j / (count - 1)
            i = f * (len(arr) - 1) * 0.84 + (len(arr) - 1) * 0.08
            i0 = int(i); t = i - i0; p = arr[i0].lerp(arr[min(i0 + 1, len(arr) - 1)], t)
            out.append(p + Vector((0, 0.009, dz)))
        return out
    MOUTH["upper"] = arc(rim_u, -0.011, 10)
    MOUTH["lower"] = arc(rim_l, 0.008, 10)


def neck(F):
    F.cap((0, 0.020, 1.540), (0, 0.010, 1.730), 0.078, 0.070, k=0.06)
    mirror(lambda sx: F.along((sx * 0.065, 0.000, 1.745), (sx * 0.025, -0.060, 1.575), 0.090, 0.018, 0.016, k=0.03))   # SCM
    mirror(lambda sx: F.ell((sx * 0.140, 0.050, 1.620), (0.140, 0.075, 0.060), rot=(0, sx * 24, 0), k=0.07))          # huge trapezius


# ---------------------------------------------------------------- torso
SHOULDER = (0.300, 0.0, 1.545)


def torso(F):
    F.ell((0, 0.010, 1.430), (0.205, 0.150, 0.200), k=0.08)            # barrel chest
    F.ell((0, 0.020, 1.555), (0.270, 0.120, 0.080), k=0.08)            # shoulder girdle
    F.ell((0, -0.050, 1.190), (0.205, 0.190, 0.185), k=0.09)           # gut
    F.ell((0, -0.060, 1.090), (0.170, 0.160, 0.090), k=0.08)           # gut sags over the belt
    F.ell((0, 0.030, 1.010), (0.205, 0.140, 0.110), k=0.08)            # pelvis
    F.ell((0, -0.236, 1.170), (0.008, 0.006, 0.010), k=0.006, neg=True)  # navel
    F.ell((0, -0.150, 1.380), (0.012, 0.012, 0.090), k=0.02, neg=True)   # sternum groove

    def side(sx):
        F.ell((sx * 0.105, -0.120, 1.480), (0.100, 0.042, 0.072), rot=(0, sx * -12, 0), k=0.04)   # pectoralis
        F.ell((sx * 0.120, -0.130, 1.405), (0.070, 0.018, 0.016), rot=(0, sx * -8, 0), k=0.03)    # pec underfold
        F.ell((sx * 0.185, 0.050, 1.400), (0.060, 0.080, 0.160), rot=(0, sx * 10, 0), k=0.07)     # latissimus
        F.ell((sx * 0.120, 0.135, 1.470), (0.075, 0.020, 0.080), rot=(0, sx * -12, 0), k=0.05)    # scapula / rhomboid
        F.ell((sx * 0.045, 0.125, 1.250), (0.035, 0.030, 0.200), k=0.05)                          # erector spinae
        F.ell((sx * 0.190, -0.020, 1.130), (0.050, 0.110, 0.090), k=0.07)                         # love handle
        F.ell((sx * 0.105, 0.110, 0.980), (0.095, 0.075, 0.100), k=0.06)                          # gluteus
        for i in range(4):                                                                        # serratus
            F.ell((sx * 0.190, -0.075 + 0.006 * i, 1.450 - 0.035 * i), (0.022, 0.014, 0.011), rot=(0, sx * -30, 0), k=0.015)
    mirror(side)


# ---------------------------------------------------------------- arms and hands
ARM_DOWN = 50.0
UPPER, FORE = 0.335, 0.295
FINGERS = [(-0.030, 0.092), (-0.010, 0.102), (0.010, 0.098), (0.029, 0.082)]


def arm_points(sx):
    s = Vector((SHOULDER[0] * sx, SHOULDER[1], SHOULDER[2]))
    a = math.radians(ARM_DOWN)
    d = Vector((sx * math.cos(a), 0.0, -math.sin(a))).normalized()
    e = s + d * UPPER
    w = e + d * FORE
    return s, e, w, d


def hand_frame(sx, d):
    inward = Vector((-sx * math.sin(math.radians(ARM_DOWN)), 0, -math.cos(math.radians(ARM_DOWN))))
    inward = (inward - d * inward.dot(d)).normalized()
    across = d.cross(inward).normalized()
    if across.y > 0:
        across = -across
    return inward, across


def arms(F):
    def side(sx):
        s, e, w, d = arm_points(sx)
        inward, across = hand_frame(sx, d)
        F.cap(s, e, 0.072, 0.058, k=0.06)
        F.cap(e, w, 0.060, 0.040, k=0.05)
        F.along(s + Vector((0, 0, 0.02)), e, 0.115, 0.082, 0.078, at=0.12, k=0.06)                 # deltoid
        F.along(s, e, 0.115, 0.050, 0.045, offset=(0, -0.030, 0), at=0.58, k=0.04)               # biceps
        F.along(s, e, 0.130, 0.052, 0.046, offset=(0, 0.032, 0), at=0.50, k=0.04)                # triceps
        F.along(e, w, 0.100, 0.044, 0.040, offset=(0, -0.012, 0), at=0.24, k=0.04)               # brachioradialis
        F.along(e, w, 0.110, 0.040, 0.036, offset=(0, 0.018, 0), at=0.30, k=0.04)                # flexors
        F.ell(e + Vector((0, 0.050, 0)), (0.018, 0.018, 0.018), k=0.02)                          # elbow
        F.ell(w, (0.030, 0.042, 0.020), rot=Vector((1, 0, 0)).rotation_difference(d), k=0.025)   # wrist
        hand(F, sx, w, d)
    mirror(side)


def hand(F, sx, w, d):
    inward, across = hand_frame(sx, d)
    q = Vector((1, 0, 0)).rotation_difference(d)
    F.ell(w + d * 0.058, (0.060, 0.054, 0.024), rot=q, k=0.02)                                     # palm
    F.ell(w + d * 0.040 - across * 0.034 + inward * 0.012, (0.036, 0.020, 0.020), rot=q, k=0.02)   # thenar
    for fi, (off, length) in enumerate(FINGERS):
        base = w + d * 0.110 + across * off * 1.55
        JOINTS[(sx, fi + 1)] = [base.copy()]
        F.ell(base - inward * 0.004, (0.0165,) * 3, k=0.01)                                       # knuckle
        dirn = rotate_toward(d, across, off * 90)
        p = base
        for i, L in enumerate((length * 0.44, length * 0.32, length * 0.24)):
            dirn = rotate_toward(dirn, inward, (14, 22, 20)[i])
            q2 = p + dirn * L
            r = (0.0145, 0.0130, 0.0115)[i]
            F.cap(p, q2, r, r * 0.92, k=0.006)
            F.ell(q2 - inward * 0.002, (r * 1.03,) * 3, k=0.005)
            p = q2
            JOINTS[(sx, fi + 1)].append(p.copy())
        NAILS.append((p.copy(), dirn.copy(), inward.copy(), 0.010))
    base = w + d * 0.035 - across * 0.046 + inward * 0.016
    dirn = rotate_toward(rotate_toward(d, across, -50), inward, 25)
    p = base
    JOINTS[(sx, 0)] = [base.copy()]
    for i, L in enumerate((0.050, 0.042, 0.034)):
        dirn = rotate_toward(dirn, inward, 12)
        q2 = p + dirn * L
        r = (0.019, 0.016, 0.014)[i]
        F.cap(p, q2, r, r * 0.9, k=0.012 if i else 0.02)
        p = q2
        JOINTS[(sx, 0)].append(p.copy())
    NAILS.append((p.copy(), dirn.copy(), inward.copy(), 0.012))


# ---------------------------------------------------------------- legs
HIP, KNEE, ANKLE = (0.135, 0.020, 0.950), (0.150, -0.010, 0.520), (0.160, 0.020, 0.095)


def legs(F):
    def side(sx):
        h = Vector((HIP[0] * sx, HIP[1], HIP[2])); kn = Vector((KNEE[0] * sx, KNEE[1], KNEE[2]))
        a = Vector((ANKLE[0] * sx, ANKLE[1], ANKLE[2]))
        F.cap(h, kn, 0.110, 0.068, k=0.07)
        F.cap(kn, a, 0.068, 0.042, k=0.05)
        F.along(h, kn, 0.170, 0.055, 0.050, offset=(0, -0.035, 0), at=0.55, k=0.04)              # quads
        F.along(h, kn, 0.090, 0.046, 0.044, offset=(sx * -0.030, -0.028, 0), at=0.82, k=0.04)    # vastus medialis
        F.along(h, kn, 0.170, 0.055, 0.050, offset=(0, 0.040, 0), at=0.50, k=0.04)               # hamstrings
        F.ell(kn + Vector((0, -0.060, 0.004)), (0.028, 0.016, 0.032), k=0.02)                   # patella
        F.along(kn, a, 0.120, 0.048, 0.050, offset=(0, 0.040, 0), at=0.28, k=0.04)               # calf
        F.ell(a + Vector((0, 0.040, -0.052)), (0.036, 0.040, 0.040), k=0.03)                    # heel
        F.ell(a + Vector((0, -0.070, -0.070)), (0.055, 0.110, 0.028), k=0.04)                   # foot
    mirror(side)


def body_field(h=0.0024):
    EYES.clear(); NAILS.clear(); JOINTS.clear(); MOUTH.clear()
    F = Field((-0.95, -0.34, -0.01), (0.95, 0.26, 1.97), h)
    torso(F); neck(F); arms(F); legs(F); head(F)
    return F
