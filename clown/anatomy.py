"""Anatomy of the clown, sculpted as a signed-distance field.
Metres, Z up, facing -Y. Proportions: 1.95 m, ~8 heads, long arms and fingers, gaunt torso."""
import math
from mathutils import Vector, Quaternion, Euler
from sdf import Field, front_y

H = 1.95
NAILS = []          # (tip, direction, palm-normal) for nail meshes
EYES = []           # (centre, radius)
MOUTH = []          # grin curve points for teeth
OPEN = []           # half-opening of the grin at each point
JOINTS = {}         # (side, finger) -> joint positions, for the skeleton


def mirror(fn):
    for sx in (1, -1):
        fn(sx)


def rotate_toward(d, toward, deg):
    axis = d.cross(toward)
    if axis.length < 1e-6:
        return d.copy()
    return (Quaternion(axis.normalized(), math.radians(deg)) @ d).normalized()


def grin(x):
    """Grin centre-line: runs nearly ear to ear and lifts at the corners (y is snapped to the face later)."""
    return Vector((x, -0.098 + 3.0 * x * x, 1.758 + 4.2 * x * x))


# ---------------------------------------------------------------- head
def head(F):
    F.ell((0, 0.010, 1.868), (0.080, 0.100, 0.083), k=0.03)          # cranium
    F.ell((0, 0.045, 1.830), (0.066, 0.064, 0.064), k=0.03)          # occiput
    F.ell((0, -0.028, 1.808), (0.064, 0.070, 0.070), k=0.03)         # face mass
    F.ell((0, -0.074, 1.880), (0.062, 0.030, 0.042), rot=(-18, 0, 0), k=0.02)   # forehead
    F.ell((0, -0.084, 1.858), (0.058, 0.018, 0.012), k=0.012)        # brow ridge
    F.ell((0, -0.026, 1.740), (0.050, 0.050, 0.028), k=0.025)        # mandible
    F.ell((0, -0.066, 1.714), (0.017, 0.016, 0.022), rot=(28, 0, 0), k=0.03)    # long pointed chin
    F.ell((0, -0.100, 1.806), (0.009, 0.016, 0.026), rot=(-14, 0, 0), k=0.008)  # nasal bridge
    F.ell((0, -0.088, 1.772), (0.034, 0.016, 0.022), k=0.014)        # muzzle

    def side(sx):
        F.ell((sx * 0.050, -0.004, 1.748), (0.016, 0.030, 0.034), k=0.016)          # jaw angle
        F.ell((sx * 0.055, -0.064, 1.812), (0.022, 0.016, 0.011), rot=(0, 0, sx * 28), k=0.01)  # zygomatic
        F.ell((sx * 0.066, -0.034, 1.817), (0.010, 0.034, 0.009), k=0.01)          # zygomatic arch
        F.ell((sx * 0.059, -0.070, 1.765), (0.019, 0.016, 0.024), k=0.012, neg=True)  # hollow cheek
        F.ell((sx * 0.077, -0.030, 1.858), (0.010, 0.024, 0.022), k=0.012, neg=True)  # temple
        F.ell((sx * 0.034, -0.098, 1.836), (0.022, 0.024, 0.016), k=0.008, neg=True)  # orbit
        F.ell((sx * 0.034, -0.090, 1.818), (0.017, 0.008, 0.005), k=0.008)          # lower-lid bag
        F.ell((sx * 0.040, -0.083, 1.796), (0.016, 0.006, 0.004), rot=(0, sx * 25, 0), k=0.004, neg=True)  # tear trough
        F.ell((sx * 0.006, -0.111, 1.778), (0.006, 0.008, 0.006), k=0.004, neg=True)  # nostril
        EYES.append((Vector((sx * 0.034, -0.085, 1.836)), 0.0140))
        F.ell((sx * 0.034, -0.088, 1.846), (0.017, 0.012, 0.0065), rot=(-18, 0, 0), k=0.007)  # heavy upper lid
        # ears: long, slightly pointed, set low
        F.ell((sx * 0.084, 0.010, 1.818), (0.008, 0.022, 0.036), rot=(10, sx * -18, 0), k=0.006)
        F.ell((sx * 0.088, 0.020, 1.852), (0.004, 0.008, 0.014), rot=(28, sx * -18, 0), k=0.012)
        F.ell((sx * 0.091, 0.006, 1.820), (0.003, 0.011, 0.020), rot=(10, sx * -18, 0), k=0.003, neg=True)
    mirror(side)

    # nasolabial folds dug in around the grin
    mirror(lambda sx: F.along((sx * 0.016, -0.104, 1.782), (sx * 0.070, -0.072, 1.758), 0.034, 0.004, 0.004,
                              k=0.006, neg=True))
    # the grin: snapped to the skin, opens wider in the middle, lips rolled around it
    MOUTH.clear()
    n = 12
    for i in range(-n, n + 1):
        p = grin(i * 0.0046)
        y = front_y(F, p.x, p.z, y0=-0.2, y1=-0.03)
        if y is None:
            continue
        p.y = y + 0.004
        MOUTH.append(p)
    N = len(MOUTH)
    OPEN.clear()
    for i in range(N):
        t = i / (N - 1) * 2 - 1
        OPEN.append(0.0016 + 0.0062 * (1 - t * t) ** 1.5)
    for i in range(N - 1):
        a, b = MOUTH[i], MOUTH[i + 1]
        oa, ob = OPEN[i], OPEN[i + 1]
        F.cap(a + Vector((0, 0.001, oa + 0.0015)), b + Vector((0, 0.001, ob + 0.0015)), 0.0040, k=0.006)    # upper lip
        F.cap(a + Vector((0, 0.000, -oa - 0.0022)), b + Vector((0, 0.000, -ob - 0.0022)), 0.0046, k=0.006)  # lower lip
    for i in range(N - 1):
        a, b = MOUTH[i], MOUTH[i + 1]
        for dy in (-0.004, 0.004, 0.012, 0.020):
            F.cap(a + Vector((0, dy, 0)), b + Vector((0, dy, 0)), OPEN[i], OPEN[i + 1], k=0.0015, neg=True)
    F.ell(MOUTH[N // 2] + Vector((0, 0.032, 0)), (0.040, 0.026, 0.014), k=0.006, neg=True)   # mouth cavity


def neck(F):
    F.cap((0, 0.012, 1.560), (0, 0.010, 1.745), 0.054, 0.042, k=0.04)
    F.ell((0, -0.030, 1.672), (0.008, 0.008, 0.012), k=0.016)                  # Adam's apple

    def side(sx):
        F.along((sx * 0.052, 0.004, 1.770), (sx * 0.016, -0.044, 1.590), 0.085, 0.010, 0.009, k=0.02)  # SCM
        F.ell((sx * 0.090, 0.040, 1.610), (0.090, 0.040, 0.030), rot=(0, sx * 22, 0), k=0.04)        # trapezius
    mirror(side)


# ---------------------------------------------------------------- torso
SHOULDER = (0.200, 0.0, 1.535)


def torso(F):
    F.ell((0, 0.008, 1.435), (0.132, 0.094, 0.150), k=0.04)        # rib cage
    F.ell((0, 0.010, 1.525), (0.180, 0.080, 0.060), k=0.05)        # shoulder girdle
    F.ell((0, 0.000, 1.225), (0.098, 0.074, 0.110), k=0.05)        # abdomen
    F.ell((0, 0.012, 1.025), (0.142, 0.094, 0.090), k=0.05)        # pelvis
    F.ell((0, -0.072, 1.150), (0.006, 0.006, 0.008), k=0.006, neg=True)  # navel
    F.ell((0, -0.082, 1.545), (0.020, 0.012, 0.030), k=0.012, neg=True)  # sternal notch
    F.ell((0, -0.086, 1.395), (0.008, 0.010, 0.090), k=0.01, neg=True)   # sternum groove

    def side(sx):
        F.ell((sx * 0.072, -0.070, 1.468), (0.068, 0.022, 0.048), rot=(0, sx * -14, 0), k=0.02)  # pectoralis
        F.along((sx * 0.020, -0.060, 1.580), (sx * 0.180, -0.014, 1.566), 0.088, 0.007, 0.007, k=0.02)  # clavicle
        s_, e_, _, _ = arm_points(sx)
        F.along(s_ + Vector((0, 0, 0.01)), e_, 0.075, 0.050, 0.046, at=0.14, k=0.035)     # deltoid
        F.ell((sx * 0.112, 0.040, 1.380), (0.034, 0.040, 0.105), rot=(0, sx * 14, 0), k=0.03)   # latissimus
        F.ell((sx * 0.090, 0.086, 1.470), (0.048, 0.010, 0.056), rot=(0, sx * -10, 0), k=0.02)  # scapula
        F.ell((sx * 0.032, 0.072, 1.250), (0.020, 0.018, 0.170), k=0.02)          # erector spinae
        F.ell((sx * 0.084, -0.016, 1.170), (0.024, 0.050, 0.068), k=0.04)         # external oblique
        F.ell((sx * 0.106, 0.010, 1.092), (0.016, 0.034, 0.012), k=0.04)          # iliac crest
        F.ell((sx * 0.076, 0.070, 0.965), (0.070, 0.052, 0.078), k=0.035)         # gluteus
        for k_ in range(3):                                                        # rectus abdominis
            F.ell((sx * 0.023, -0.066, 1.322 - 0.058 * k_), (0.019, 0.006, 0.023), k=0.02)
        for i in range(6):                                                         # serratus fingers
            F.ell((sx * 0.118, -0.030 + 0.004 * i, 1.445 - 0.028 * i), (0.016, 0.010, 0.008),
                  rot=(0, sx * -30, 0), k=0.008)
        C, A = Vector((0, 0.008, 1.435)), Vector((0.132, 0.094, 0.150))
        for i in range(6):                                                         # ribs showing through
            z0 = 1.395 - 0.030 * i
            pts = []
            for j in range(9):
                f = j / 8
                th = math.radians(-20 - 55 * f)                                    # side -> front
                z = z0 - 0.035 * f
                sc = math.sqrt(max(0.0, 1 - ((z - C.z) / A.z) ** 2))
                p = Vector((sx * A.x * sc * math.cos(th), C.y + A.y * sc * math.sin(th), z))
                n = Vector(((p.x) / A.x ** 2, (p.y - C.y) / A.y ** 2, (p.z - C.z) / A.z ** 2)).normalized()
                pts.append(p - n * 0.0045)
            for a, b in zip(pts, pts[1:]):
                F.cap(a, b, 0.0048, k=0.01)
    mirror(side)


# ---------------------------------------------------------------- arms and hands
ARM_DOWN = 45.0
UPPER, FORE = 0.335, 0.305
FINGERS = [(-0.026, 0.135), (-0.009, 0.158), (0.008, 0.148), (0.024, 0.120)]


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
        F.cap(s, e, 0.036, 0.030, k=0.03)
        F.cap(e, w, 0.031, 0.020, k=0.025)
        F.along(s, e, 0.105, 0.030, 0.026, offset=(0, -0.020, 0), at=0.58, k=0.02)    # biceps
        F.along(s, e, 0.120, 0.032, 0.028, offset=(0, 0.022, 0), at=0.50, k=0.02)     # triceps
        F.along(e, w, 0.090, 0.022, 0.020, offset=(0, -0.010, 0), at=0.26, k=0.018)   # brachioradialis
        F.along(e, w, 0.100, 0.020, 0.018, offset=(0, 0.012, 0), at=0.32, k=0.018)    # flexors
        F.ell(e + Vector((0, 0.030, 0)), (0.011, 0.011, 0.011), k=0.01)              # olecranon
        F.ell(w, (0.017, 0.024, 0.011), rot=Vector((1, 0, 0)).rotation_difference(d), k=0.012)  # wrist
        hand(F, sx, w, d)
    mirror(side)


def hand(F, sx, w, d):
    inward, across = hand_frame(sx, d)
    q = Vector((1, 0, 0)).rotation_difference(d)
    palm_c = w + d * 0.052
    F.ell(palm_c, (0.050, 0.040, 0.013), rot=Quaternion(d, 0) @ q, k=0.012)
    F.ell(palm_c - d * 0.006 - across * 0.026 + inward * 0.008, (0.030, 0.012, 0.012), rot=q, k=0.01)  # thenar
    for fi, (off, length) in enumerate(FINGERS):
        base = w + d * 0.098 + across * off * 1.6
        JOINTS[(sx, fi + 1)] = [base.copy()]
        F.ell(base - inward * 0.003, (0.0105, 0.0105, 0.0105), k=0.008)                        # knuckle
        segs = (length * 0.45, length * 0.32, length * 0.23)
        dirn = rotate_toward(d, across, off * 120)
        p = base
        for i, L in enumerate(segs):
            dirn = rotate_toward(dirn, inward, (10, 18, 22)[i])
            q2 = p + dirn * L
            r = (0.0088, 0.0076, 0.0064)[i]
            F.cap(p, q2, r, r * 0.88, k=0.004)
            F.ell(q2 - inward * 0.0015, (r * 1.02,) * 3, k=0.003)                          # joint knob
            p = q2
            JOINTS[(sx, fi + 1)].append(p.copy())
        NAILS.append((p.copy(), dirn.copy(), inward.copy()))
    base = w + d * 0.030 - across * 0.036 + inward * 0.012
    dirn = rotate_toward(rotate_toward(d, across, -55), inward, 25)
    p = base
    JOINTS[(sx, 0)] = [base.copy()]
    for i, L in enumerate((0.046, 0.040, 0.034)):
        dirn = rotate_toward(dirn, inward, 12)
        q2 = p + dirn * L
        r = (0.0125, 0.0100, 0.0084)[i]
        F.cap(p, q2, r, r * 0.9, k=0.006 if i else 0.012)
        p = q2
        JOINTS[(sx, 0)].append(p.copy())
    NAILS.append((p.copy(), dirn.copy(), inward.copy()))


# ---------------------------------------------------------------- legs
HIP, KNEE, ANKLE = (0.098, 0.005, 0.955), (0.112, -0.010, 0.520), (0.122, 0.020, 0.090)


def legs(F):
    def side(sx):
        h = Vector((HIP[0] * sx, HIP[1], HIP[2]))
        kn = Vector((KNEE[0] * sx, KNEE[1], KNEE[2]))
        a = Vector((ANKLE[0] * sx, ANKLE[1], ANKLE[2]))
        F.cap(h, kn, 0.064, 0.042, k=0.04)
        F.cap(kn, a, 0.040, 0.024, k=0.03)
        F.along(h, kn, 0.170, 0.034, 0.030, offset=(0, -0.026, 0), at=0.55, k=0.02)        # rectus femoris
        F.along(h, kn, 0.150, 0.030, 0.026, offset=(sx * 0.030, -0.008, 0), at=0.55, k=0.02)  # vastus lateralis
        F.along(h, kn, 0.080, 0.028, 0.026, offset=(sx * -0.022, -0.020, 0), at=0.82, k=0.02)  # vastus medialis
        F.along(h, kn, 0.170, 0.032, 0.028, offset=(0, 0.028, 0), at=0.50, k=0.02)         # hamstrings
        F.along(h, kn, 0.130, 0.028, 0.026, offset=(sx * -0.034, 0.0, 0), at=0.30, k=0.025)  # adductors
        F.ell(kn + Vector((0, -0.036, 0.004)), (0.019, 0.011, 0.023), k=0.01)              # patella
        F.along(kn, a, 0.110, 0.026, 0.026, offset=(sx * 0.012, 0.028, 0), at=0.28, k=0.018)   # gastrocnemius
        F.along(kn, a, 0.120, 0.027, 0.028, offset=(sx * -0.012, 0.030, 0), at=0.30, k=0.018)
        F.along(kn, a, 0.200, 0.009, 0.009, offset=(0, -0.024, 0), at=0.5, k=0.012)        # tibia
        F.ell(a + Vector((sx * 0.020, 0, 0)), (0.011,) * 3, k=0.008)                       # malleoli
        F.ell(a + Vector((-sx * 0.016, 0, 0.004)), (0.011,) * 3, k=0.008)
        F.ell(a + Vector((0, 0.036, -0.048)), (0.025, 0.030, 0.030), k=0.02)               # heel
        F.ell(a + Vector((0, -0.060, -0.064)), (0.040, 0.085, 0.022), k=0.025)             # foot
        for t in range(5):
            F.ell(a + Vector((sx * (-0.026 + 0.013 * t), -0.148 + 0.008 * abs(t - 1), -0.072)),
                  (0.0085 - 0.0008 * t, 0.016, 0.008), k=0.006)
    mirror(side)


def body_field(h=0.0022):
    NAILS.clear(); EYES.clear(); JOINTS.clear()
    F = Field((-0.92, -0.26, -0.01), (0.92, 0.16, 1.99), h)
    head(F); neck(F); torso(F); arms(F); legs(F)
    return F
