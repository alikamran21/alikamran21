"""Draws the Pac-Man contribution game (game_dark.svg / game_light.svg).

Everything runs on one timeline, so the eaten boxes, the counter and the
progress bar always agree: Pac-Man sweeps the contribution grid column by
column, each contribution box disappears the moment he reaches it, and when
the board is clear an easter egg shows before the game restarts.
"""
import datetime
import os
from xml.sax.saxutils import escape

HERE = os.path.dirname(os.path.abspath(__file__))

STEP = 0.05          # seconds Pac-Man spends per grid cell
EGG = 5.0            # seconds the easter egg stays on screen
TAIL = 0.6           # pause before the loop restarts

THEMES = {
    "dark": dict(page="#0d1117", empty="#161b22", levels=["#0e4429", "#006d32", "#26a641", "#39d353"],
                 text="#c9d1d9", muted="#8b949e", track="#21262d", pac="#facc15", bar="#39d353"),
    "light": dict(page="#ffffff", empty="#ebedf0", levels=["#9be9a8", "#40c463", "#30a14e", "#216e39"],
                  text="#24292f", muted="#57606a", track="#d0d7de", pac="#eab308", bar="#30a14e"),
}
FONT = "-apple-system, 'Segoe UI', Helvetica, Arial, sans-serif"
W = 1000
LEFT = 24
TOP = 30
ROW_LABEL_H = 0


def frac(t, total):
    return min(1.0, max(0.0, t / total))


def kt(values):
    return ";".join(f"{v:.5f}".rstrip("0").rstrip(".") if v not in (0, 1) else str(int(v)) for v in values)


def level_of(count, cuts):
    if count <= 0:
        return -1
    for i, c in enumerate(cuts):
        if count <= c:
            return i
    return len(cuts)


def ghost(color, eye_dx=0):
    return (f'<path d="M-7 7 V-1 A7 7 0 0 1 7 -1 V7 L4.7 5 L2.3 7 L0 5 L-2.3 7 L-4.7 5 Z" fill="{color}"/>'
            f'<circle cx="-2.5" cy="-1.5" r="2" fill="#fff"/><circle cx="2.5" cy="-1.5" r="2" fill="#fff"/>'
            f'<circle cx="{-2.5 + eye_dx}" cy="-1.5" r="1" fill="#1e3a8a"/><circle cx="{2.5 + eye_dx}" cy="-1.5" r="1" fill="#1e3a8a"/>')


def render(theme, stats, mode="anim"):
    """mode: 'anim' (real file), 'start' or 'egg' (static previews for checking the layout)."""
    c = THEMES[theme]
    cal = sorted((datetime.date.fromisoformat(d), n) for d, n in stats["calendar"])
    ncols = (len(cal) + 6) // 7
    pitch = (W - 2 * LEFT) / ncols
    cell = pitch - 3.4
    gh = 7 * pitch
    bar_y = TOP + gh + 30
    H = int(bar_y + 34)

    def cx(col):
        return LEFT + col * pitch + cell / 2

    def cy(row):
        return TOP + row * pitch + cell / 2

    nz = sorted(n for _, n in cal if n > 0)
    cuts = [nz[int(len(nz) * q) - 1] for q in (0.25, 0.5, 0.75)] if len(nz) >= 4 else [1, 2, 3]

    # route: down one column, up the next
    route = []
    for col in range(ncols):
        rows = range(7) if col % 2 == 0 else range(6, -1, -1)
        for r in rows:
            if col * 7 + r < len(cal):
                route.append((col, r))
    E = (len(route) - 1) * STEP
    T = E + 0.4 + EGG + TAIL
    eaten = []  # (time, col, row)
    for k, (col, r) in enumerate(route):
        if cal[col * 7 + r][1] > 0:
            eaten.append((k * STEP, col, r))
    M = len(eaten)

    # corners of the path (direction changes)
    corners = [0]
    for k in range(1, len(route) - 1):
        d1 = (route[k][0] - route[k - 1][0], route[k][1] - route[k - 1][1])
        d2 = (route[k + 1][0] - route[k][0], route[k + 1][1] - route[k][1])
        if d1 != d2:
            corners.append(k)
    corners.append(len(route) - 1)

    def angle(k):
        k2 = min(k + 1, len(route) - 1)
        d = (route[k2][0] - route[k][0], route[k2][1] - route[k][1])
        return {(0, 1): 90, (0, -1): -90, (1, 0): 0}.get(d, 0)

    anim = mode == "anim"
    o = [f'<?xml version="1.0" encoding="UTF-8"?>',
         f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="{FONT}">',
         "<title>Contribution Pac-Man</title>",
         f'<rect width="{W}" height="{H}" fill="{c["page"]}"/>']

    # month labels (skip a leading partial month that would collide with the next one)
    marks, last = [], None
    for col in range(ncols):
        d = cal[min(col * 7, len(cal) - 1)][0]
        if d.month != last:
            marks.append((col, d.strftime("%b")))
            last = d.month
    if len(marks) > 1 and marks[1][0] - marks[0][0] < 3:
        marks = marks[1:]
    for col, name in marks:
        if col * pitch + LEFT < W - 40:
            o.append(f'<text x="{LEFT + col * pitch:.1f}" y="{TOP - 10}" font-size="10" fill="{c["muted"]}">{name}</text>')

    # cells (+ overlay that "eats" them)
    eat_at = {(col, r): t for t, col, r in eaten}
    for i, (d, n) in enumerate(cal):
        col, r = divmod(i, 7)
        lv = level_of(n, cuts)
        x, y = LEFT + col * pitch, TOP + r * pitch
        fill = c["empty"] if lv < 0 else c["levels"][lv]
        o.append(f'<rect x="{x:.2f}" y="{y:.2f}" width="{cell:.2f}" height="{cell:.2f}" rx="3" fill="{fill}"/>')
        if lv >= 0:
            if anim:
                ft = frac(eat_at[(col, r)], T)
                o.append(f'<rect x="{x:.2f}" y="{y:.2f}" width="{cell:.2f}" height="{cell:.2f}" rx="3" fill="{c["empty"]}" opacity="0">'
                         f'<animate attributeName="opacity" calcMode="discrete" values="0;1;1" keyTimes="0;{ft:.5f};1" dur="{T:.2f}s" repeatCount="indefinite"/></rect>')
            elif mode == "egg":
                o.append(f'<rect x="{x:.2f}" y="{y:.2f}" width="{cell:.2f}" height="{cell:.2f}" rx="3" fill="{c["empty"]}"/>')

    # ghosts (decorative, own loops)
    gw = ncols * pitch
    for color, row, dur, begin, dx in (("#ef4444", 2, 11, 0, 1), ("#22d3ee", 5, 14, -6, -1)):
        y = cy(row)
        x0, x1 = LEFT + cell / 2, LEFT + gw - cell / 2 - 3
        if anim:
            o.append(f'<g><animateTransform attributeName="transform" type="translate" values="{x0:.1f},{y:.1f};{x1:.1f},{y:.1f};{x0:.1f},{y:.1f}" '
                     f'dur="{dur}s" begin="{begin}s" repeatCount="indefinite"/>{ghost(color, dx)}</g>')
        elif mode == "start":
            o.append(f'<g transform="translate({(x0 + x1) / 2:.1f},{y:.1f})">{ghost(color, dx)}</g>')

    # Pac-Man
    mouth = (f'<polygon points="0,0 9,-6 9,6" fill="{c["page"]}">'
             f'<animate attributeName="points" values="0,0 9,-6 9,6;0,0 9,-0.8 9,0.8;0,0 9,-6 9,6" dur="0.45s" repeatCount="indefinite"/></polygon>')
    pac_body = f'<circle r="7.6" fill="{c["pac"]}"/>{mouth}'
    if anim:
        pos = ";".join(f"{cx(route[k][0]):.1f},{cy(route[k][1]):.1f}" for k in corners) \
            + f";{cx(route[-1][0]):.1f},{cy(route[-1][1]):.1f}"
        times = [frac(k * STEP, T) for k in corners] + [1.0]
        angs = ";".join(str(angle(k)) for k in corners) + f";{angle(corners[-1])}"
        hide = frac(E + 0.4, T)
        o.append(f'<g opacity="1"><animate attributeName="opacity" calcMode="discrete" values="1;0;0" keyTimes="0;{hide:.5f};1" dur="{T:.2f}s" repeatCount="indefinite"/>'
                 f'<animateTransform attributeName="transform" type="translate" values="{pos}" keyTimes="{kt(times)}" dur="{T:.2f}s" repeatCount="indefinite"/>'
                 f'<g><animateTransform attributeName="transform" type="rotate" calcMode="discrete" values="{angs}" keyTimes="{kt(times)}" dur="{T:.2f}s" repeatCount="indefinite"/>'
                 f'{pac_body}</g></g>')
    elif mode == "start":
        o.append(f'<g transform="translate({cx(route[0][0]):.1f},{cy(route[0][1]):.1f}) rotate(90)">{pac_body}</g>')

    # progress bar + counter (same timeline as the game)
    bw = W - 2 * LEFT
    o.append(f'<text x="{LEFT}" y="{bar_y - 8}" font-size="12" fill="{c["muted"]}">Boxes eaten</text>')
    o.append(f'<rect x="{LEFT}" y="{bar_y}" width="{bw}" height="8" rx="4" fill="{c["track"]}"/>')
    if anim:
        vals = [0] + [bw * (i + 1) / M for i in range(M)] + [bw]
        ts = [0.0] + [frac(t, T) for t, _, _ in eaten] + [1.0]
        o.append(f'<rect x="{LEFT}" y="{bar_y}" width="0" height="8" rx="4" fill="{c["bar"]}">'
                 f'<animate attributeName="width" values="{";".join(f"{v:.1f}" for v in vals)}" keyTimes="{kt(ts)}" dur="{T:.2f}s" repeatCount="indefinite"/></rect>')
        for k in range(M + 1):
            a = frac(eaten[k - 1][0], T) if k > 0 else 0.0
            b = frac(eaten[k][0], T) if k < M else 1.0
            if k == 0:
                vv, kk = "1;0;0", f"0;{b:.5f};1"
            elif k == M:
                vv, kk = "0;1;1", f"0;{a:.5f};1"
            else:
                vv, kk = "0;1;0;0", f"0;{a:.5f};{b:.5f};1"
            o.append(f'<text x="{LEFT + bw}" y="{bar_y - 8}" font-size="12" font-weight="600" text-anchor="end" fill="{c["text"]}" opacity="{1 if k == 0 else 0}">{k} / {M}'
                     f'<animate attributeName="opacity" calcMode="discrete" values="{vv}" keyTimes="{kk}" dur="{T:.2f}s" repeatCount="indefinite"/></text>')
    else:
        done = M if mode == "egg" else 0
        o.append(f'<rect x="{LEFT}" y="{bar_y}" width="{bw * done / M:.1f}" height="8" rx="4" fill="{c["bar"]}"/>')
        o.append(f'<text x="{LEFT + bw}" y="{bar_y - 8}" font-size="12" font-weight="600" text-anchor="end" fill="{c["text"]}">{done} / {M}</text>')

    # easter egg
    mx, my = W / 2, TOP + gh / 2
    steam = "".join(
        f'<path d="M{sx} -26 q-4 -6 0 -12 q4 -6 0 -12" fill="none" stroke="{c["muted"]}" stroke-width="2" stroke-linecap="round" opacity=".5">'
        + (f'<animate attributeName="opacity" values=".15;.8;.15" dur="1.8s" begin="{b}s" repeatCount="indefinite"/>' if anim else "") + "</path>"
        for sx, b in ((-8, 0), (0, 0.5), (8, 1.0)))
    egg = (f'<rect x="{LEFT - 6}" y="{TOP - 6}" width="{bw + 12}" height="{gh + 10}" rx="6" fill="{c["page"]}" opacity=".9"/>'
           f'<g transform="translate({mx},{my - 4})">{steam}'
           f'<path d="M-22 -18 H22 V-2 A22 22 0 0 1 -22 -2 Z" fill="#b8763e"/>'
           f'<path d="M22 -12 h6 a8 8 0 0 1 0 16 h-7" fill="none" stroke="#b8763e" stroke-width="4"/>'
           f'<rect x="-30" y="24" width="60" height="4" rx="2" fill="{c["muted"]}"/></g>'
           f'<text x="{mx}" y="{my + 50}" font-size="15" font-weight="700" letter-spacing="3" text-anchor="middle" fill="{c["text"]}">COFFEEBEAN WAS HERE</text>'
           f'<text x="{mx}" y="{my + 69}" font-size="11" text-anchor="middle" fill="{c["muted"]}">level clear · {M} boxes eaten · restarting</text>')
    if anim:
        a = frac(E + 0.6, T)
        d = 0.03
        o.append(f'<g opacity="0"><animate attributeName="opacity" values="0;0;1;1;0;0" '
                 f'keyTimes="0;{a:.5f};{a + d:.5f};{frac(E + 0.4 + EGG - 0.4, T):.5f};{frac(E + 0.4 + EGG, T):.5f};1" '
                 f'dur="{T:.2f}s" repeatCount="indefinite"/>{egg}</g>')
    elif mode == "egg":
        o.append(f'<g>{egg}</g>')

    o.append("</svg>")
    return "\n".join(o) + "\n"


def build(stats):
    if not stats.get("calendar"):
        print("no calendar data yet; skipping game")
        return
    for theme in ("dark", "light"):
        with open(os.path.join(HERE, f"game_{theme}.svg"), "w") as f:
            f.write(render(theme, stats))
    print("wrote game_dark.svg and game_light.svg")
