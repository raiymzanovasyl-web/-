#!/usr/bin/env python3
"""
Генератор эскизного чертежа капсульного дома 8500 x 3300 мм (лист A2, М 1:50).

Выходные файлы (папка output/):
  capsule_house.svg  – чертёж (план, фасады, разрез, экспликация, ТЭП, штамп)
  capsule_house.dxf  – та же графика для AutoCAD / nanoCAD / КОМПАС (1 ед. = 1 мм натуры)
Запуск:  python3 generate_capsule_house.py   (только стандартная библиотека Python 3)
PDF/PNG: node render_capsule_house.js  (через Playwright/Chromium, по желанию)
"""
import math
import os

# ------------------------------------------------------------------ ПАРАМЕТРЫ (мм натуры)
L, B = 8500.0, 3300.0          # длина и ширина корпуса
H_BODY = 3200.0                # высота корпуса
Z0 = 400.0                     # низ корпуса над землёй (опоры + обвязка)
FLOOR = 600.0                  # уровень чистого пола от земли (±0.000)
CEIL = 3400.0                  # потолок от земли (высота помещений 2800)
T = 120.0                      # толщина оболочки (алюминий + PU 100 + отделка)
TP = 80.0                      # толщина перегородок
R_PLAN = 600.0                 # скругление углов в плане
R_SIDE_TOP, R_SIDE_BOT = 1400.0, 500.0   # скругления на продольном фасаде
R_END_TOP, R_END_BOT = 900.0, 500.0      # скругления поперечного сечения
TERRACE = 1500.0               # глубина террасы перед панорамным остеклением
SILL, WIN_TOP = 1400.0, 2650.0 # низ/верх боковых окон от земли (+0.800 / +2.050)

SCALE = 50.0                   # М 1:50
SHEET_W, SHEET_H = 594.0, 420.0  # A2
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
NAME = "capsule_house"

# ------------------------------------------------------------------ ПРИМИТИВЫ
svg = []   # элементы SVG (координаты листа, мм, Y вниз)
dxf = []   # сущности DXF (мм натуры, Y вверх)

STYLE = {  # класс -> (слой DXF, толщина линии на листе)
    "k": ("CONTOUR", 0.5), "m": ("VISIBLE", 0.3), "t": ("THIN", 0.18),
    "d": ("DIMS", 0.13), "ax": ("AXES", 0.13), "hid": ("HIDDEN", 0.18),
    "txt": ("TEXT", 0),
}


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def to_dxf(p):
    return p[0] * SCALE, (SHEET_H - p[1]) * SCALE


def s_poly(pts, cls="t", closed=False, fill="none", extra=""):
    tag = "polygon" if closed else "polyline"
    svg.append(f'<{tag} class="{cls}" fill="{fill}" {extra} points="' +
               " ".join(f"{x:.2f},{y:.2f}" for x, y in pts) + '"/>')
    layer = STYLE[cls][0]
    dxf.extend(["0", "POLYLINE", "8", layer, "66", "1", "70", "1" if closed else "0"])
    for p in pts:
        x, y = to_dxf(p)
        dxf.extend(["0", "VERTEX", "8", layer, "10", f"{x:.2f}", "20", f"{y:.2f}", "30", "0"])
    dxf.extend(["0", "SEQEND", "8", layer])


def s_line(a, b, cls="t"):
    svg.append(f'<line class="{cls}" x1="{a[0]:.2f}" y1="{a[1]:.2f}" x2="{b[0]:.2f}" y2="{b[1]:.2f}"/>')
    (x1, y1), (x2, y2) = to_dxf(a), to_dxf(b)
    dxf.extend(["0", "LINE", "8", STYLE[cls][0], "10", f"{x1:.2f}", "20", f"{y1:.2f}", "30", "0",
                "11", f"{x2:.2f}", "21", f"{y2:.2f}", "31", "0"])


def s_circle(c, r, cls="t", fill="none"):
    svg.append(f'<circle class="{cls}" fill="{fill}" cx="{c[0]:.2f}" cy="{c[1]:.2f}" r="{r:.2f}"/>')
    x, y = to_dxf(c)
    dxf.extend(["0", "CIRCLE", "8", STYLE[cls][0], "10", f"{x:.2f}", "20", f"{y:.2f}", "30", "0",
                "40", f"{r * SCALE:.2f}"])


def s_text(p, s, size=2.5, anchor="middle", rot=0, bold=False):
    tr = f' transform="rotate({rot} {p[0]:.2f} {p[1]:.2f})"' if rot else ""
    fw = ' font-weight="bold"' if bold else ""
    svg.append(f'<text x="{p[0]:.2f}" y="{p[1]:.2f}" font-size="{size}" text-anchor="{anchor}"{fw}{tr}>'
               f'{esc(s)}</text>')
    x, y = to_dxf(p)
    just = {"start": 0, "middle": 1, "end": 2}[anchor]
    dxf.extend(["0", "TEXT", "8", "TEXT", "10", f"{x:.2f}", "20", f"{y:.2f}", "30", "0",
                "40", f"{size * 0.72 * SCALE:.2f}", "1", s, "50", f"{-rot}", "72", str(just),
                "11", f"{x:.2f}", "21", f"{y:.2f}", "31", "0"])


def rrect(x0, y0, x1, y1, rbl, rbr, rtr, rtl, n=14):
    """Скруглённый прямоугольник (радиусы по углам), против часовой стрелки."""
    pts = []
    for cx, cy, r, a0 in ((x0 + rbl, y0 + rbl, rbl, 180), (x1 - rbr, y0 + rbr, rbr, 270),
                          (x1 - rtr, y1 - rtr, rtr, 0), (x0 + rtl, y1 - rtl, rtl, 90)):
        for i in range(n + 1):
            a = math.radians(a0 + 90 * i / n)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


class View:
    """Вид в масштабе 1:50; (ox, oy) – положение начала координат вида на листе."""

    def __init__(self, ox, oy):
        self.ox, self.oy = ox, oy

    def P(self, x, y):
        return self.ox + x / SCALE, self.oy - y / SCALE

    def poly(self, pts, cls="t", closed=True, fill="none", extra=""):
        s_poly([self.P(*p) for p in pts], cls, closed, fill, extra)

    def rect(self, x0, y0, x1, y1, cls="t", fill="none", extra=""):
        self.poly([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], cls, True, fill, extra)

    def line(self, a, b, cls="t"):
        s_line(self.P(*a), self.P(*b), cls)

    def text(self, x, y, s, size=2.5, anchor="middle", rot=0, bold=False):
        s_text(self.P(x, y), s, size, anchor, rot, bold)

    def circle(self, x, y, r, cls="t", fill="none"):
        s_circle(self.P(x, y), r / SCALE, cls, fill)

    def arc(self, cx, cy, r, a0, a1, cls="t", n=24):
        pts = [(cx + r * math.cos(math.radians(a0 + (a1 - a0) * i / n)),
                cy + r * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]
        self.poly(pts, cls, closed=False)

    def hatched(self, outer, inner=None, pattern="hatch", cls="k"):
        """Заливка штриховкой (только SVG) + контуры."""
        d = "M" + " L".join(f"{self.P(*p)[0]:.2f},{self.P(*p)[1]:.2f}" for p in outer) + " Z"
        if inner:
            d += " M" + " L".join(f"{self.P(*p)[0]:.2f},{self.P(*p)[1]:.2f}" for p in inner) + " Z"
        svg.append(f'<path d="{d}" fill="url(#{pattern})" fill-rule="evenodd" stroke="none"/>')
        self.poly(outer, cls)
        if inner:
            self.poly(inner, cls)

    def blank(self, x0, y0, x1, y1):
        """Белая «вырезка» (проём в стене) – только SVG."""
        a, b = self.P(x0, y0), self.P(x1, y1)
        svg.append(f'<rect x="{min(a[0], b[0]):.2f}" y="{min(a[1], b[1]):.2f}" '
                   f'width="{abs(a[0] - b[0]):.2f}" height="{abs(a[1] - b[1]):.2f}" fill="#fff"/>')

    # ---- размеры
    def _tick(self, p):
        x, y = self.P(*p)
        s_line((x - 1.1, y + 1.1), (x + 1.1, y - 1.1), "m")

    def dim_h(self, xs, yd, y_from=None, lift=0.9):
        for x in xs:
            if y_from is not None:
                a, b = self.P(x, y_from), self.P(x, yd)
                sgn = 1 if b[1] > a[1] else -1
                s_line((a[0], a[1] + sgn * 1.0), (b[0], b[1] + sgn * 1.5), "d")
            self._tick((x, yd))
        a, b = self.P(xs[0], yd), self.P(xs[-1], yd)
        s_line((a[0] - 1.5, a[1]), (b[0] + 1.5, b[1]), "d")
        for x1, x2 in zip(xs, xs[1:]):
            m = self.P((x1 + x2) / 2, yd)
            s_text((m[0], m[1] - lift), f"{x2 - x1:.0f}", 2.5)

    def dim_v(self, ys, xd, x_from=None):
        for y in ys:
            if x_from is not None:
                a, b = self.P(x_from, y), self.P(xd, y)
                sgn = 1 if b[0] > a[0] else -1
                s_line((a[0] + sgn * 1.0, a[1]), (b[0] + sgn * 1.5, b[1]), "d")
            self._tick((xd, y))
        a, b = self.P(xd, ys[0]), self.P(xd, ys[-1])
        s_line((a[0], a[1] + 1.5), (b[0], b[1] - 1.5), "d")
        for y1, y2 in zip(ys, ys[1:]):
            m = self.P(xd, (y1 + y2) / 2)
            s_text((m[0] - 0.9, m[1]), f"{y2 - y1:.0f}", 2.5, rot=-90)

    def axis(self, x, y, label, x2, y2):
        """Координационная ось от (x, y) до кружка в (x2, y2)."""
        a, b = self.P(x, y), self.P(x2, y2)
        L_ = math.dist(a, b)
        ux, uy = (b[0] - a[0]) / L_, (b[1] - a[1]) / L_
        s_line(a, (b[0] - ux * 3.5, b[1] - uy * 3.5), "ax")
        s_circle(b, 3.5, "m", "#fff")
        s_text((b[0], b[1] + 1.25), label, 3.5)

    def level(self, x, z, label, right=True):
        """Высотная отметка: треугольник на уровне z, полка с текстом."""
        px, py = self.P(x, z)
        s_poly([(px - 1.3, py - 1.8), (px + 1.3, py - 1.8), (px, py)], "t", True, "#000")
        sgn = 1 if right else -1
        s_line((px, py), (px, py - 4.5), "t")
        s_line((px, py - 4.5), (px + sgn * 13, py - 4.5), "t")
        s_text((px + sgn * 1.0, py - 5.3), label, 2.5, "start" if right else "end")

    def leader(self, x, y, tx, ty, lines, right=True):
        a, b = self.P(x, y), (self.ox + tx, self.oy + ty)
        s_circle(a, 0.5, "t", "#000")
        s_line(a, b, "t")
        w = max(len(s) for s in lines) * 1.25 + 1
        sgn = 1 if right else -1
        s_line(b, (b[0] + sgn * w, b[1]), "t")
        for i, s in enumerate(lines):
            s_text((b[0] + sgn * 0.6, b[1] - 0.8 if i == 0 else b[1] + 2.7 * i),
                   s, 2.2, "start" if right else "end")

    def title(self, x, y, s, sub=None):
        px, py = self.P(x, y)
        s_text((px, py), s, 4.2, bold=True)
        w = len(s) * 2.15
        s_line((px - w / 2, py + 1.2), (px + w / 2, py + 1.2), "m")
        if sub:
            s_text((px, py + 5.5), sub, 2.8)


def window_plan(v, side, a, b):
    """Окно в наружной стене плана: side = 'S' (y=0), 'N' (y=B), 'E' (x=L)."""
    if side in "SN":
        y0, y1 = (0, T) if side == "S" else (B - T, B)
        v.blank(a, y0 - 5, b, y1 + 5)
        for x in (a, b):
            v.line((x, y0), (x, y1), "k")
        for y in (y0, y1):
            v.line((a, y), (b, y), "t")
        v.rect(a, (y0 + y1) / 2 - 15, b, (y0 + y1) / 2 + 15, "t", "#cfe6f7")
    else:
        x0, x1 = L - T, L
        v.blank(x0 - 5, a, x1 + 5, b)
        for y in (a, b):
            v.line((x0, y), (x1, y), "k")
        for x in (x0, x1):
            v.line((x, a), (x, b), "t")
        v.rect((x0 + x1) / 2 - 15, a, (x0 + x1) / 2 + 15, b, "t", "#cfe6f7")


# ------------------------------------------------------------------ ПЛАН
def draw_plan(v):
    v.title(L / 2, B + 2300, "ПЛАН", "М 1:50")

    # терраса (под стенами)
    v.rect(L, 0, L + TERRACE, B, "m", "#f4e6c8")
    x = L + 140
    while x < L + TERRACE:
        v.line((x, 0), (x, B), "t")
        x += 140
    v.poly([(L, 40), (L + TERRACE - 40, 40), (L + TERRACE - 40, B - 40), (L, B - 40)], "m", False)
    v.poly([(L, 80), (L + TERRACE - 80, 80), (L + TERRACE - 80, B - 80), (L, B - 80)], "t", False)

    # крыльцо (3 ступени)
    v.rect(1900, -900, 3000, 0, "m")
    for y in (-300, -600):
        v.line((1900, y), (3000, y), "t")

    # оболочка
    outer = rrect(0, 0, L, B, R_PLAN, R_PLAN, R_PLAN, R_PLAN)
    inner = rrect(T, T, L - T, B - T, R_PLAN - T, R_PLAN - T, R_PLAN - T, R_PLAN - T)
    v.hatched(outer, inner)

    # перегородки
    v.hatched([(T, 1360), (900, 1360), (900, 1440), (T, 1440)], cls="m")
    v.hatched([(1600, 1360), (1840, 1360), (1840, B - T), (1760, B - T), (1760, 1440), (1600, 1440)], cls="m")
    v.hatched([(5660, 2150), (5740, 2150), (5740, B - T), (5660, B - T)], cls="m")
    v.line((5700, T), (5700, 2150), "hid")  # штора-перегородка

    # окна
    for a, b in ((3300, 5300), (6200, 7900)):
        window_plan(v, "S", a, b)
    for a, b in ((2000, 4000), (4600, 7900)):
        window_plan(v, "N", a, b)
    window_plan(v, "E", 600, B - 600)
    # раздвижная дверь на террасу в панорамном остеклении
    v.line((L - 30, 1250), (L - 30, 2050), "m")
    v.line((L - 90, 1650), (L - 90, 2450), "m")

    # входная дверь 900 (открывание внутрь)
    v.blank(2000, -5, 2900, T + 5)
    for x_ in (2000, 2900):
        v.line((x_, 0), (x_, T), "k")
    v.line((2900, T), (2900, T + 900), "m")
    v.arc(2900, T, 900, 90, 180, "t")
    # дверь в санузел 700
    v.blank(900, 1355, 1600, 1445)
    v.line((1600, 1400), (1600, 700), "m")
    v.arc(1600, 1400, 700, 180, 270, "t")

    # мебель / оборудование
    v.rect(T, 600, 700, 1300, "t")                       # шкаф в прихожей
    v.line((T, 600), (700, 1300), "t")
    v.rect(T, 2280, 1020, B - T, "t")                    # душ
    v.line((T, 2280), (1020, B - T), "t")
    v.line((T, B - T), (1020, 2280), "t")
    v.rect(1350, 2990, 1700, B - T, "t")                 # унитаз
    v.poly([(1525 + 170 * math.cos(math.radians(a)), 2760 + 230 * math.sin(math.radians(a)))
            for a in range(0, 360, 15)], "t")
    v.rect(T, 1600, 560, 2100, "t")                      # раковина
    v.poly([(330 + 140 * math.cos(math.radians(a)), 1850 + 180 * math.sin(math.radians(a)))
            for a in range(0, 360, 15)], "t")
    v.rect(1840, B - T - 600, 4300, B - T, "t")          # кухонный блок
    v.rect(1840, B - T - 650, 2440, B - T, "t")          # холодильник
    v.text(2140, 2750, "Х", 2.5)
    v.circle(2800, 2880, 130)
    v.circle(3150, 2880, 130)
    v.rect(3500, 2680, 3950, 3080, "t")                  # мойка
    v.rect(3500, 1250, 4700, 2000, "t")                  # обеденный стол
    v.rect(3500, T, 5500, 1000, "t")                     # диван
    v.rect(3500, T, 5500, 320, "t")
    v.rect(5850, 850, 7850, 2450, "t")                   # кровать 1600x2000
    v.rect(5900, 900, 6250, 1600, "t")
    v.rect(5900, 1700, 6250, 2400, "t")
    v.rect(5850, 350, 6250, 750, "t")                    # тумбы
    v.rect(5850, 2550, 6250, 2950, "t")
    v.rect(3900, 1150, 5300, 2250, "hid")                # люк-окно в кровле (над)

    # номера помещений
    for n, x_, y_ in ((1, 1050, 950), (2, 1150, 1950), (3, 2750, 1850), (4, 7000, 2800), (5, L + 750, 1650)):
        v.circle(x_, y_, 230, "m", "#fff")
        v.text(x_, y_ - 85, str(n), 2.8)
        v.text(x_, y_ - 600, f"{ROOMS[n - 1][2]:.2f}", 2.4)
        v.line((x_ - 300, y_ - 360), (x_ + 300, y_ - 360), "t")

    # разрез 1-1
    for y_a, y_b in ((-750, -300), (B + 300, B + 750)):
        v.line((5000, y_a), (5000, y_b), "k")
    for y_ in (-750, B + 750):
        v.line((5000, y_), (5450, y_), "k")
        tip = v.P(5450, y_)
        s_poly([tip, (tip[0] - 1.8, tip[1] - 0.7), (tip[0] - 1.8, tip[1] + 0.7)], "t", True, "#000")
        v.text(5250, y_ + 120, "1", 3.2)

    # размеры
    v.dim_h([0, 2000, 2900, 3300, 5300, 6200, 7900, L], -1250, 0)
    v.dim_h([0, L, L + TERRACE], -1850, None)
    v.dim_h([0, 1800, 5700, L, L + TERRACE], B + 700, B)
    v.dim_v([0, 1400, B], -700, 0)
    v.dim_v([0, B], -1300, None)

    # оси
    for x_, lab in ((0, "1"), (L, "2"), (L + TERRACE, "3")):
        v.axis(x_, -900 if x_ != 0 else -100, lab, x_, -2450)
    v.axis(-100, 0, "А", -1900, 0)
    v.axis(-100, B, "Б", -1900, B)


# ------------------------------------------------------------------ ФАСАД 1–3 (продольный)
def ground(v, x0, x1):
    v.hatched([(x0, -180), (x1, -180), (x1, 0), (x0, 0)], pattern="earth", cls="t")
    v.line((x0, 0), (x1, 0), "k")


def pile(v, x):
    v.rect(x - 54, 0, x + 54, 250, "m")
    v.rect(x - 125, 250, x + 125, 300, "m")
    v.line((x - 54, 0), (x - 54, -150), "hid")
    v.line((x + 54, 0), (x + 54, -150), "hid")


def draw_side(v):
    v.title(L / 2, 4700, "ФАСАД 1–3", "М 1:50")
    ground(v, -600, L + TERRACE + 400)
    for x in (500, 2800, 5700, 8000, L + TERRACE - 150):
        pile(v, x)
    v.rect(300, 300, 8200, Z0, "m")                     # обвязка
    # терраса и ограждение
    v.rect(L, 300, L + TERRACE, 450, "m", "#f4e6c8")
    v.rect(L + 40, 450, L + TERRACE - 40, 1550, "t", "#cfe6f7", 'fill-opacity="0.45"')
    v.line((L, 1550), (L + TERRACE, 1550), "k")
    # крыльцо
    for i in range(3):
        v.rect(1900 + i * 0, i * 200, 3000, (i + 1) * 200, "m")
    # корпус
    body = rrect(0, Z0, L, Z0 + H_BODY, R_SIDE_BOT, R_SIDE_BOT, R_SIDE_TOP, R_SIDE_TOP)
    v.poly(body, "k", fill="#eef1f4")
    led = rrect(150, Z0 + 150, L - 150, Z0 + H_BODY - 150, R_SIDE_BOT - 150, R_SIDE_BOT - 150,
                R_SIDE_TOP - 150, R_SIDE_TOP - 150)
    v.poly(led, "hid")
    v.line((300, 900), (L - 300, 900), "t")             # линия цоколя-юбки
    # люк в кровле
    v.poly(rrect(3900, Z0 + H_BODY - 10, 5300, Z0 + H_BODY + 90, 0, 0, 80, 80, 6), "m", fill="#cfe6f7")
    # окна
    for a, b in ((3300, 5300), (6200, 7900)):
        v.poly(rrect(a, SILL, b, WIN_TOP, 120, 120, 120, 120, 6), "m", fill="#cfe6f7")
        v.line(((a + b) / 2, SILL), ((a + b) / 2, WIN_TOP), "t")
        v.line((a + 250, WIN_TOP - 200), (a + 650, SILL + 300), "t")
    # дверь
    v.rect(2000, FLOOR, 2900, FLOOR + 2100, "m", "#dfe3e8")
    v.rect(2150, FLOOR + 700, 2350, FLOOR + 1950, "t", "#cfe6f7")
    v.line((2780, FLOOR + 950), (2780, FLOOR + 1250), "m")
    # панорамный торец (вид сбоку)
    v.line((L - 120, Z0 + 600), (L - 120, Z0 + H_BODY - 900), "t")
    # выноски
    v.leader(6000, Z0 + H_BODY - 150, 175, -84, ["LED-контур"], True)
    v.leader(4600, 3500, 30, -86, ["Люк-окно в кровле"], False)
    v.leader(L + 700, 1200, 194, -42, ["Стеклянное", "ограждение h=1100"], True)
    # отметки
    v.level(-300, 0, "−0,600", False)
    v.level(-300, FLOOR, "±0,000", False)
    v.level(-300, Z0 + H_BODY, "+3,000", False)
    v.level(-300, SILL, "+0,800", False)
    v.level(-300, WIN_TOP, "+2,050", False)
    v.line((-300, Z0 + H_BODY), (R_SIDE_TOP * 0.3, Z0 + H_BODY), "d")
    v.line((-300, FLOOR), (0, FLOOR), "d")
    # размеры
    v.dim_h([0, L, L + TERRACE], -650, None)
    v.dim_v([0, Z0, Z0 + H_BODY], L + TERRACE + 1300, None)
    for x_, lab in ((0, "1"), (L, "2"), (L + TERRACE, "3")):
        v.axis(x_, -200, lab, x_, -1250)


# ------------------------------------------------------------------ ФАСАД А–Б (торец)
def draw_end(v):
    v.title(B / 2, 4700, "ФАСАД А–Б", "М 1:50")
    ground(v, -300, B + 300)
    for x in (300, B - 300):
        pile(v, x)
    v.poly(rrect(0, Z0, B, Z0 + H_BODY, R_END_BOT, R_END_BOT, R_END_TOP, R_END_TOP), "k", fill="#eef1f4")
    v.poly(rrect(150, Z0 + 150, B - 150, Z0 + H_BODY - 150, 350, 350, 750, 750), "hid")
    glass = rrect(300, 700, B - 300, Z0 + H_BODY - 250, 150, 150, 650, 650)
    v.poly(glass, "m", fill="#cfe6f7")
    for y in (1250, 2050):
        v.line((y, 700), (y, FLOOR + 2300), "m")
    v.line((300, FLOOR + 2300), (B - 300, FLOOR + 2300), "m")
    v.line((1650, 700), (1650, FLOOR + 2300), "t")
    # терраса и ограждение
    v.rect(0, 300, B, 450, "m", "#f4e6c8")
    v.rect(40, 450, B - 40, 1550, "t", "#cfe6f7", 'fill-opacity="0.45"')
    v.line((0, 1550), (B, 1550), "k")
    v.leader(1650, 2600, 80, -78, ["Панорамное", "остекление Low-E"], True)
    v.leader(1650, 1000, 76, -26, ["Раздвижная дверь"], True)
    v.dim_h([0, B], -650, None)
    v.dim_v([0, Z0, Z0 + H_BODY], -800, None)
    v.axis(0, -200, "А", 0, -1250)
    v.axis(B, -200, "Б", B, -1250)


# ------------------------------------------------------------------ РАЗРЕЗ 1–1
def draw_section(v):
    v.title(B / 2, 4700, "РАЗРЕЗ 1–1", "М 1:50")
    ground(v, -300, B + 300)
    for x in (300, B - 300):
        pile(v, x)
    v.rect(300, 300, B - 300, Z0, "m")
    # вид за плоскостью сечения: панорамное остекление
    v.poly(rrect(300, 700, B - 300, Z0 + H_BODY - 250, 150, 150, 650, 650), "t", fill="#eaf4fb")
    # оболочка в сечении
    outer = rrect(0, Z0, B, Z0 + H_BODY, R_END_BOT, R_END_BOT, R_END_TOP, R_END_TOP)
    inner = rrect(T, FLOOR, B - T, CEIL + 80, 150, 150, R_END_TOP - T, R_END_TOP - T)
    v.hatched(outer, inner)
    # люк в кровле (х 3900–5300 пересекается сечением х=5000; y 1150–2250)
    h0, h1 = B - 2250, B - 1150
    v.blank(h0, CEIL + 70, h1, Z0 + H_BODY + 10)
    v.line((h0, CEIL + 80), (h0, Z0 + H_BODY + 90), "k")
    v.line((h1, CEIL + 80), (h1, Z0 + H_BODY + 90), "k")
    v.rect(h0, Z0 + H_BODY + 40, h1, Z0 + H_BODY + 90, "m", "#cfe6f7")
    # окна в продольных стенах
    for x0, x1 in ((0, T), (B - T, B)):
        v.blank(x0 - 5, SILL, x1 + 5, WIN_TOP)
        v.line((x0, SILL), (x1, SILL), "k")
        v.line((x0, WIN_TOP), (x1, WIN_TOP), "k")
        v.rect((x0 + x1) / 2 - 15, SILL, (x0 + x1) / 2 + 15, WIN_TOP, "t", "#cfe6f7")
    # подвесной потолок с LED-нишами
    v.line((T + 600, CEIL), (h0, CEIL), "m")
    v.line((h1, CEIL), (B - T - 600, CEIL), "m")
    # пол
    v.line((T, FLOOR + 25), (B - T, FLOOR + 25), "t")
    # диван (сечением х=5000 – вдоль стены y=0 → справа)
    v.rect(B - T - 880, FLOOR, B - T, FLOOR + 450, "t")
    v.rect(B - T - 200, FLOOR + 450, B - T, FLOOR + 850, "t")
    # кровать за сечением
    v.rect(B - 2450, FLOOR, B - 850, FLOOR + 500, "t")
    # выноски
    v.leader(30, 3000, -10, -90, ["Оболочка 120: алюминий 3 мм +", "PU 100 мм + панели WPC"], False)
    v.leader(1000, FLOOR + 12, -12, -14, ["Пол: SPC 5, фанера 18,", "утеплитель 100, каркас"], False)
    v.leader(1650, Z0 + H_BODY + 60, 70, -88, ["Люк-окно"], True)
    v.level(B + 300, FLOOR, "±0,000", True)
    v.level(B + 300, CEIL, "+2,800", True)
    v.level(B + 300, 0, "−0,600", True)
    v.line((B - T, CEIL), (B + 300, CEIL), "d")
    v.line((B - T, FLOOR), (B + 300, FLOOR), "d")
    v.dim_h([0, T, B - T, B], -650, None)
    v.dim_v([FLOOR, CEIL], 1650, None)
    v.axis(0, -200, "Б", 0, -1250)
    v.axis(B, -200, "А", B, -1250)


# ------------------------------------------------------------------ ТАБЛИЦЫ
def room_area(x0, y0, x1, y1, corners, r=R_PLAN - T):
    return ((x1 - x0) * (y1 - y0) - corners * (1 - math.pi / 4) * r * r) / 1e6


ROOMS = [
    (1, "Прихожая", room_area(T, T, 1760, 1360, 1)),
    (2, "Санузел (душ, с/у, умывальник)", room_area(T, 1440, 1760, B - T, 1)),
    (3, "Кухня-гостиная", room_area(1840, T, 5700, B - T, 0) - (B - T - 2150) * 40 / 1e6),
    (4, "Спальная зона", room_area(5700, T, L - T, B - T, 2) - (B - T - 2150) * 40 / 1e6),
    (5, "Терраса (летнее, k=0,3)", TERRACE * B / 1e6),
]


def table(x, y, title, cols, rows, row_h=5.5):
    s_text((x + sum(cols) / 2, y - 2), title, 3.2, bold=True)
    W_ = sum(cols)
    H_ = row_h * len(rows)
    s_poly([(x, y), (x + W_, y), (x + W_, y + H_), (x, y + H_)], "k", True)
    for i in range(1, len(rows)):
        s_line((x, y + i * row_h), (x + W_, y + i * row_h), "k" if i == 1 else "t")
    cx = x
    for c in cols[:-1]:
        cx += c
        s_line((cx, y), (cx, y + H_), "k")
    for i, row in enumerate(rows):
        cx = x
        for j, (c, val) in enumerate(zip(cols, row)):
            if j == 0 or (i == 0):
                s_text((cx + c / 2, y + i * row_h + row_h * 0.68), val, 2.5, "middle", bold=(i == 0))
            elif j == len(cols) - 1 and len(cols) > 2:
                s_text((cx + c - 1.5, y + i * row_h + row_h * 0.68), val, 2.5, "end")
            else:
                s_text((cx + 1.5, y + i * row_h + row_h * 0.68), val, 2.5, "start")
            cx += c


def draw_tables():
    living = sum(r[2] for r in ROOMS[:4])
    rows = [("№", "Наименование", "Площадь, м²")]
    rows += [(str(n), name, f"{a:.2f}") for n, name, a in ROOMS]
    rows += [("", "Итого общая площадь (без террасы)", f"{living:.2f}"),
             ("", "Итого с террасой (k=0,3)", f"{living + ROOMS[4][2] * 0.3:.2f}")]
    table(316, 28, "Экспликация помещений", [10, 98, 26], rows)

    tep = [("Показатель", "Значение"),
           ("Габариты корпуса Д×Ш×В", f"{L:.0f}×{B:.0f}×{H_BODY:.0f} мм"),
           ("Высота от земли / помещений", f"{Z0 + H_BODY:.0f} / {CEIL - FLOOR:.0f} мм"),
           ("Площадь застройки (с террасой)", f"{(L + TERRACE) * B / 1e6:.1f} м²"),
           ("Каркас", "сварной, сталь оцинк. 100×50×3"),
           ("Наружная обшивка", "алюминий 3 мм, покраска PVDF"),
           ("Утеплитель", "PU-панели 100 мм, λ≈0,022"),
           ("Остекление", "закалён. Low-E 6+12Ar+6+12Ar+6"),
           ("Внутренняя отделка", "панели WPC, пол SPC 5 мм"),
           ("Инженерия", "220 В / 8 кВт, сплит-система"),
           ("", "водонагр. 60 л, тёплый пол в с/у"),
           ("Опоры", "винтовые сваи Ø108, 10 шт."),
           ("Масса модуля (ориент.)", "≈ 8,5 т")]
    table(316, 94, "Технические характеристики", [62, 72], tep, 5.2)


def draw_notes(x, y):
    s_text((x, y), "Примечания", 3.2, "start", bold=True)
    notes = [
        "1. Размеры – в мм, отметки – в м. За отметку ±0,000 принят уровень чистого пола (+600 мм от земли).",
        "2. Корпус – заводской модуль полной готовности; доставка тралом (ширина 3,3 м – негабарит),",
        "    монтаж краном на опоры с обвязкой из швеллера 16П, крепление болтами М16.",
        "3. Глубину и шаг свай уточнить по геологии участка; сети (вода, канализация, кабель) – снизу, в",
        "    утеплённом коробе через обвязку.",
        "4. Эскизный проект. Для рабочей документации – расчёт каркаса на снег/ветер района строительства.",
    ]
    for i, s in enumerate(notes):
        s_text((x, y + 5 + i * 4.2), s, 2.5, "start")


def draw_frame_and_stamp():
    s_poly([(20, 5), (SHEET_W - 5, 5), (SHEET_W - 5, SHEET_H - 5), (20, SHEET_H - 5)], "k", True)
    # основная надпись 185×55 (упрощённая форма 1 ГОСТ Р 21.101)
    x0, y0 = SHEET_W - 5 - 185, SHEET_H - 5 - 55
    s_poly([(x0, y0), (x0 + 185, y0), (x0 + 185, y0 + 55), (x0, y0 + 55)], "k", True)
    for cx in (7, 17, 40, 55, 65):
        s_line((x0 + cx, y0), (x0 + cx, y0 + 55), "k" if cx in (65,) else "t")
    for i in range(1, 11):
        s_line((x0, y0 + i * 5), (x0 + 65, y0 + i * 5), "t")
    s_line((x0 + 65, y0 + 15), (x0 + 185, y0 + 15), "k")
    s_line((x0 + 65, y0 + 40), (x0 + 185, y0 + 40), "k")
    s_line((x0 + 135, y0 + 15), (x0 + 135, y0 + 55), "k")
    s_line((x0 + 135, y0 + 20), (x0 + 185, y0 + 20), "k")
    for cx in (150, 165):
        s_line((x0 + cx, y0 + 15), (x0 + cx, y0 + 25), "k")
    s_line((x0 + 135, y0 + 25), (x0 + 185, y0 + 25), "k")
    for i, s in enumerate(("Разраб.", "Пров.", "Н. контр.", "Утв.")):
        s_text((x0 + 1, y0 + 29 + i * 5), s, 2.2, "start")
    for cx, s in ((3.5, "Изм."), (12, "Кол."), (28.5, "Лист"), (47.5, "№док."), (60, "Дата")):
        s_text((x0 + cx, y0 + 24), s, 2.0)
    s_text((x0 + 125, y0 + 9.5), "КД-01-АР", 5, bold=True)
    s_text((x0 + 100, y0 + 24), "Капсульный жилой модуль", 3.5)
    s_text((x0 + 100, y0 + 30), f"{L:.0f}×{B:.0f} мм с террасой", 3.5)
    s_text((x0 + 100, y0 + 36), "(эскизный проект)", 3.0)
    s_text((x0 + 100, y0 + 46), "План, фасады, разрез 1–1,", 3.0)
    s_text((x0 + 100, y0 + 51), "экспликация, ТЭП", 3.0)
    for cx, s in ((142.5, "Стадия"), (157.5, "Лист"), (175, "Листов")):
        s_text((x0 + cx, y0 + 18.8), s, 2.2)
    for cx, s in ((142.5, "ЭП"), (157.5, "1"), (175, "1")):
        s_text((x0 + cx, y0 + 23.8), s, 3.0)
    s_text((x0 + 160, y0 + 35), "М 1:50", 5, bold=True)
    s_text((SHEET_W - 30, SHEET_H - 1.5), "Формат A2", 2.5)


# ------------------------------------------------------------------ ВЫВОД
def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    draw_frame_and_stamp()
    draw_plan(View(62, 122))
    draw_side(View(62, 290))
    draw_end(View(325, 290))
    draw_section(View(438, 290))
    draw_tables()
    draw_notes(26, 330)

    head = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{SHEET_W}mm" height="{SHEET_H}mm" viewBox="0 0 {SHEET_W} {SHEET_H}">
<defs>
<pattern id="hatch" width="1.4" height="1.4" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
<rect width="1.4" height="1.4" fill="#fff"/><line x1="0" y1="0" x2="0" y2="1.4" stroke="#000" stroke-width="0.13"/></pattern>
<pattern id="earth" width="2.2" height="2.2" patternUnits="userSpaceOnUse" patternTransform="rotate(-45)">
<rect width="2.2" height="2.2" fill="#fff"/><line x1="0" y1="0" x2="0" y2="1.1" stroke="#555" stroke-width="0.15"/></pattern>
<style>
text {{ font-family: "ISOCPEUR", "GOST type A", "DejaVu Sans", Arial, sans-serif; font-style: italic; fill: #000; }}
.k {{ stroke:#000; stroke-width:0.5; stroke-linejoin:round; }}
.m {{ stroke:#000; stroke-width:0.3; stroke-linejoin:round; }}
.t {{ stroke:#000; stroke-width:0.18; }}
.d {{ stroke:#000; stroke-width:0.13; }}
.ax {{ stroke:#000; stroke-width:0.13; stroke-dasharray:6 1.2 0.6 1.2; }}
.hid {{ stroke:#000; stroke-width:0.18; stroke-dasharray:1.6 0.8; fill:none; }}
</style></defs>
<rect width="{SHEET_W}" height="{SHEET_H}" fill="#fff"/>'''
    with open(os.path.join(OUT_DIR, NAME + ".svg"), "w", encoding="utf-8") as fh:
        fh.write(head + "\n" + "\n".join(svg) + "\n</svg>\n")

    layers = sorted({v[0] for v in STYLE.values()})
    d = ["0", "SECTION", "2", "HEADER", "9", "$INSUNITS", "70", "4", "0", "ENDSEC",
         "0", "SECTION", "2", "TABLES", "0", "TABLE", "2", "LAYER", "70", str(len(layers))]
    for ly in layers:
        d += ["0", "LAYER", "2", ly, "70", "0", "62", "7", "6", "CONTINUOUS"]
    d += ["0", "ENDTAB", "0", "ENDSEC", "0", "SECTION", "2", "ENTITIES"] + dxf + ["0", "ENDSEC", "0", "EOF", ""]
    with open(os.path.join(OUT_DIR, NAME + ".dxf"), "w", encoding="cp1251", errors="replace") as fh:
        fh.write("\n".join(d))

    living = sum(r[2] for r in ROOMS[:4])
    print(f"Корпус {L:.0f}×{B:.0f}×{H_BODY:.0f} мм, общая площадь {living:.2f} м², "
          f"терраса {ROOMS[4][2]:.2f} м²")
    print(f"Записано: output/{NAME}.svg, output/{NAME}.dxf")


if __name__ == "__main__":
    main()
