#!/usr/bin/env python3
"""
Генератор управляющей программы (G-code) для лазерной резки
декоративной панели забора «Ёлочка» 2400 x 1500 мм, лист 2–3 мм.

Выходные файлы (папка output/):
  panel_2400x1500.nc   – G-code с учётом ширины реза (керфа), подводами и порядком резки
  panel_2400x1500.dxf  – чистая геометрия (без керфа) для CypCut / FSCUT / LaserCAD и т.п.
  panel_2400x1500.svg  – превью для проверки рисунка
Запуск:  python3 generate_panel.py   (только стандартная библиотека Python 3)
"""
import math
import os

# ------------------------------------------------------------------ ПАРАМЕТРЫ
W, H = 2400.0, 1500.0          # габарит панели, мм (по чертежу)
FRAME = 50.0                   # ширина рамки по периметру
COLS = 4                       # количество «ёлочек» по ширине
DIVIDER = 30.0                 # ширина вертикальной перемычки между ёлочками
TRUNK = 30.0                   # ширина «ствола» ёлочки
SLAT = 30.0                    # ширина диагональной ламели (перпендикулярно)
GAP = 45.0                     # ширина прорези (перпендикулярно)
MIN_HOLE_AREA = 900.0          # мелкие обрезки-треугольники не режем, мм²

THICKNESS = 3.0                # толщина листа, мм (2 или 3)
KERF = 0.25                    # ширина реза, мм (компенсация kerf/2)
LEAD_IN = 5.0                  # длина подвода, мм
# Режимы (ориентир для волоконного лазера 1–2 кВт, сталь Ст3, газ O2/воздух)
FEED = {2.0: 4500, 3.0: 3200}[THICKNESS]   # рабочая подача, мм/мин
POWER = 1000                               # S – мощность, (Вт или % по контроллеру)
PIERCE_DELAY = {2.0: 0.3, 3.0: 0.6}[THICKNESS]  # пауза на прожиг, с
RAPID = 20000                              # холостой ход, мм/мин (для оценки времени)
LASER_ON = f"M3 S{POWER}"
LASER_OFF = "M5"

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
NAME = "panel_2400x1500"

# ------------------------------------------------------------------ ГЕОМЕТРИЯ
# Многоугольник задаётся пересечением полуплоскостей (nx, ny, c): nx*x + ny*y <= c.
# Это позволяет точно смещать контур на kerf/2 (сдвигом каждой полуплоскости).
BIG = [(-1, 0, 1e6), (1, 0, 1e6), (0, -1, 1e6), (0, 1, 1e6)]


def clip(poly, hp):
    nx, ny, c = hp
    out = []
    n = len(poly)
    for i in range(n):
        p, q = poly[i], poly[(i + 1) % n]
        dp = nx * p[0] + ny * p[1] - c
        dq = nx * q[0] + ny * q[1] - c
        if dp <= 0:
            out.append(p)
        if dp * dq < 0:
            t = dp / (dp - dq)
            out.append((p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1])))
    return out


def polygon(halfplanes, shrink=0.0):
    poly = [(-1e6, -1e6), (1e6, -1e6), (1e6, 1e6), (-1e6, 1e6)]
    for nx, ny, c in halfplanes:
        L = math.hypot(nx, ny)
        poly = clip(poly, (nx / L, ny / L, c / L - shrink))
        if len(poly) < 3:
            return []
    # убрать совпадающие вершины
    res = []
    for p in poly:
        if not res or math.dist(p, res[-1]) > 1e-6:
            res.append(p)
    if len(res) > 1 and math.dist(res[0], res[-1]) < 1e-6:
        res.pop()
    return res


def area(poly):
    return abs(sum(poly[i][0] * poly[(i + 1) % len(poly)][1] -
                   poly[(i + 1) % len(poly)][0] * poly[i][1]
                   for i in range(len(poly)))) / 2


def rect_hp(x0, y0, x1, y1):
    return [(-1, 0, -x0), (1, 0, x1), (0, -1, -y0), (0, 1, y1)]


def build_holes():
    """Возвращает список отверстий, каждое – набор полуплоскостей."""
    holes = []
    inner_w = W - 2 * FRAME
    col_w = (inner_w - (COLS - 1) * DIVIDER) / COLS
    half_w = (col_w - TRUNK) / 2
    y0, y1 = FRAME, H - FRAME
    pitch = SLAT + GAP
    s2 = math.sqrt(2)
    for ci in range(COLS):
        cx0 = FRAME + ci * (col_w + DIVIDER)
        axis = cx0 + col_w / 2                # ось ствола
        # Левая половина: ветви «\» (идут от ствола вверх-влево), u = (y - (axis - x)) / √2
        # Правая половина – зеркально: u = (y - (x - axis)) / √2
        for side in (-1, 1):
            if side < 0:
                rx0, rx1 = cx0, axis - TRUNK / 2
            else:
                rx0, rx1 = axis + TRUNK / 2, cx0 + col_w
            rect = rect_hp(rx0, y0, rx1, y1)
            # u = (y + side*(axis - x)) / √2  ->  нормаль (−side, 1)/√2
            # Диапазон u на прямоугольнике
            us = [(yy + side * (axis - xx)) / s2 for xx in (rx0, rx1) for yy in (y0, y1)]
            umin, umax = min(us), max(us)
            k = math.floor((umin - (y0 / s2)) / pitch) - 1
            while True:
                a = y0 / s2 + k * pitch + SLAT / 2    # фаза: зеркальна для обеих сторон
                b = a + GAP
                if a > umax:
                    break
                # a <= u <= b, где u*√2 = y - side*x + side*axis
                band = [(side, -1, -(a * s2) + side * axis),      # u >= a
                        (-side, 1, b * s2 - side * axis)]         # u <= b
                hp = rect + band
                poly = polygon(hp)
                if poly and area(poly) >= MIN_HOLE_AREA:
                    holes.append(hp)
                k += 1
    return holes


# ------------------------------------------------------------------ ТРАЕКТОРИИ
def start_and_lead(poly, inside=True):
    """Точка входа на середине самой длинной стороны и точка прожига внутри отхода."""
    n = len(poly)
    i = max(range(n), key=lambda j: math.dist(poly[j], poly[(j + 1) % n]))
    p, q = poly[i], poly[(i + 1) % n]
    m = ((p[0] + q[0]) / 2, (p[1] + q[1]) / 2)
    cx = sum(v[0] for v in poly) / n
    cy = sum(v[1] for v in poly) / n
    d = math.dist(m, (cx, cy))
    L = min(LEAD_IN, d * 0.6)
    sgn = 1 if inside else -1
    pierce = (m[0] + sgn * (cx - m[0]) / d * L, m[1] + sgn * (cy - m[1]) / d * L)
    # обход: от середины ребра i к вершине i+1 и далее по кругу
    path = [m] + [poly[(i + 1 + j) % n] for j in range(n)] + [m]
    return pierce, path


def orient(poly, ccw):
    s = sum(poly[i][0] * poly[(i + 1) % len(poly)][1] -
            poly[(i + 1) % len(poly)][0] * poly[i][1] for i in range(len(poly)))
    return poly if (s > 0) == ccw else poly[::-1]


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    r = KERF / 2
    hole_hps = build_holes()
    nominal_holes = [polygon(hp) for hp in hole_hps]
    cut_holes = [polygon(hp, shrink=r) for hp in hole_hps]   # отверстие сужаем на kerf/2

    # Порядок резки: ближайший сосед от начала координат
    order, cur, left = [], (0.0, 0.0), list(range(len(cut_holes)))
    while left:
        j = min(left, key=lambda k: math.dist(cur, cut_holes[k][0]))
        order.append(j)
        left.remove(j)
        cur = cut_holes[j][0]

    jobs = []
    for j in order:
        poly = orient(cut_holes[j], ccw=False)   # внутренние – по часовой (G41-эквивалент)
        jobs.append(("hole", *start_and_lead(poly, inside=True)))
    outer = orient([(-r, -r), (W + r, -r), (W + r, H + r), (-r, H + r)], ccw=True)
    jobs.append(("outer", *start_and_lead(outer, inside=False)))   # наружный – последним

    # ---------------- G-code (комментарии ASCII – не все стойки понимают кириллицу)
    g = []
    cut_len = travel = 0.0
    pos = (0.0, 0.0)
    f = lambda v: f"{v:.3f}".rstrip("0").rstrip(".")
    g += [f"( FENCE PANEL HERRINGBONE {int(W)}x{int(H)} MM, SHEET {THICKNESS} MM )",
          f"( HOLES: {len(jobs) - 1}, OUTER CONTOUR: 1 )",
          f"( KERF {KERF} MM ALREADY COMPENSATED - DO NOT USE G41/G42 )",
          f"( ZERO: LOWER LEFT CORNER. MIN SHEET {int(W)+20}x{int(H)+20} MM )",
          "G21", "G90", "G17", LASER_OFF]
    for idx, (kind, pierce, path) in enumerate(jobs, 1):
        g.append(f"( {idx}: {'HOLE' if kind == 'hole' else 'OUTER CONTOUR'} )")
        g.append(f"G0 X{f(pierce[0])} Y{f(pierce[1])}")
        travel += math.dist(pos, pierce)
        g += [LASER_ON, f"G4 P{PIERCE_DELAY}"]
        g.append(f"G1 X{f(path[0][0])} Y{f(path[0][1])} F{FEED}")
        cut_len += math.dist(pierce, path[0])
        for a, b in zip(path, path[1:]):
            g.append(f"G1 X{f(b[0])} Y{f(b[1])}")
            cut_len += math.dist(a, b)
        g.append(LASER_OFF)
        pos = path[-1]
    g += ["G0 X0 Y0", "M30", ""]
    t_min = cut_len / FEED + travel / RAPID + len(jobs) * (PIERCE_DELAY + 0.5) / 60
    g.insert(2, f"( CUT LENGTH {cut_len/1000:.1f} M, EST. TIME {t_min:.0f} MIN PER PANEL )")
    with open(os.path.join(OUT_DIR, NAME + ".nc"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(g))

    # ---------------- DXF (R12, номинальная геометрия без керфа)
    d = ["0", "SECTION", "2", "HEADER", "9", "$INSUNITS", "70", "4", "0", "ENDSEC",
         "0", "SECTION", "2", "ENTITIES"]

    def dxf_poly(pts, layer):
        d.extend(["0", "POLYLINE", "8", layer, "66", "1", "70", "1"])
        for x, y in pts:
            d.extend(["0", "VERTEX", "8", layer, "10", f"{x:.4f}", "20", f"{y:.4f}", "30", "0"])
        d.extend(["0", "SEQEND", "8", layer])
    for p in nominal_holes:
        dxf_poly(p, "CUT_INNER")
    dxf_poly([(0, 0), (W, 0), (W, H), (0, H)], "CUT_OUTER")
    d += ["0", "ENDSEC", "0", "EOF", ""]
    with open(os.path.join(OUT_DIR, NAME + ".dxf"), "w") as fh:
        fh.write("\n".join(d))

    # ---------------- SVG превью (Y вверх как в станке)
    pad = 60
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{-pad} {-pad} {W+2*pad} {H+2*pad+80}" '
         f'width="1200">',
         f'<rect x="{-pad}" y="{-pad}" width="{W+2*pad}" height="{H+2*pad+80}" fill="#fff"/>',
         f'<rect x="0" y="0" width="{W}" height="{H}" fill="#3a3f45"/>']
    for p in nominal_holes:
        s.append('<polygon fill="#fff" points="' +
                 " ".join(f"{x:.2f},{H - y:.2f}" for x, y in p) + '"/>')
    s.append(f'<text x="{W/2}" y="{H+60}" font-size="44" text-anchor="middle" '
             f'font-family="sans-serif">{int(W)} x {int(H)} мм, отверстий: {len(nominal_holes)}, '
             f'рез {cut_len/1000:.1f} м, ~{t_min:.0f} мин</text></svg>')
    with open(os.path.join(OUT_DIR, NAME + ".svg"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(s))

    print(f"Отверстий: {len(nominal_holes)}")
    print(f"Длина реза: {cut_len/1000:.1f} м, холостые: {travel/1000:.1f} м, ~{t_min:.0f} мин/панель")
    print(f"Открытая площадь: {sum(map(area, nominal_holes))/(W*H)*100:.0f}%")


if __name__ == "__main__":
    main()
