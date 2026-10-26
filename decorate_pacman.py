"""Frames the generated Pac-Man SVGs in the same terminal card as the header.

Usage: python decorate_pacman.py <dir containing pacman-contribution-graph*.svg>

The game file already says, for every contribution box, the exact moment it is
eaten (a fill animation on the box). This script:
  1. plays the game SPEED times faster and stretches the loop by EXTRA seconds,
     rescaling every animation so the game itself is untouched otherwise,
  2. puts the board in a card with the header's colours and monospace type
     (dimmer walls, month labels in the same font),
  3. adds a "boxes eaten" bar and counter driven by those same eat times,
  4. shows the easter egg (easter_egg.png) once the board is clear, then the
     loop restarts the game.
If the file does not look the way this script expects, it is left untouched.
"""
import base64
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SPEED = 0.6          # game time multiplier (0.6 = plays 1.67x faster)
EXTRA = 8.0          # seconds added to the loop for the easter egg

ANIM_TAG = re.compile(r"<(animate|animateTransform)\b[^>]*>", re.S)

# same palette and type as build_header.py / build_tracker.py
THEMES = {
    "dark": dict(bg="#161b22", text="#c9d1d9", key="#ffa657", val="#a5d6ff", dots="#616e7f",
                 border="#30363d", track="#21262d", bar="#39d353", wall="#2f4a6d",
                 empty_from="#161b22", empty="#21262d"),
    "light": dict(bg="#f6f8fa", text="#24292f", key="#953800", val="#0a3069", dots="#a8b3c1",
                  border="#d0d7de", track="#e1e4e8", bar="#30a14e", wall="#9fb7d9",
                  empty_from="#ebedf0", empty="#ebedf0"),
}
FONT = "Consolas, 'Liberation Mono', Menlo, 'DejaVu Sans Mono', monospace"
W = 1000
PAD = 20
CW = 8.0              # px per character
COLS = int((W - 2 * PAD) / CW)


def fnum(x):
    s = f"{x:.6f}".rstrip("0").rstrip(".")
    return s or "0"


def parse_events(svg):
    """(fraction, col, row) for every box that gets eaten."""
    ev = []
    pat = re.compile(r'<rect id="c-(\d+)-(\d+)"[^>]*>\s*<animate attributeName="fill"[^>]*?keyTimes="([^"]*)"', re.S)
    for m in pat.finditer(svg):
        kts = [float(x) for x in m.group(3).split(";")]
        if len(kts) >= 2:
            ev.append((kts[1], int(m.group(1)), int(m.group(2))))
    ev.sort()
    return ev


def rescale(svg, d_old, d_new, sc):
    """Point every game animation at the new loop length; `sc` maps old fractions to new ones."""
    old_dur = f'dur="{d_old}ms"'
    count = 0

    def fix(m):
        nonlocal count
        tag = m.group(0)
        if old_dur not in tag:
            return tag
        kt = re.search(r'keyTimes="([^"]*)"', tag)
        vals = re.search(r'values="([^"]*)"', tag, re.S)
        if not kt or not vals:
            return tag
        kts = [float(x) for x in kt.group(1).split(";")]
        vs = [v.strip() for v in vals.group(1).split(";")]
        if len(kts) != len(vs):
            return tag
        new_kts = [fnum(k * sc) for k in kts] + ["1"]
        new_vs = vs + [vs[-1]]
        tag = tag.replace(kt.group(0), f'keyTimes="{";".join(new_kts)}"')
        tag = tag.replace(vals.group(0), f'values="{";".join(new_vs)}"')
        tag = tag.replace(old_dur, f'dur="{d_new}ms"')
        count += 1
        return tag

    return ANIM_TAG.sub(fix, svg), count


def text(x, y, parts, anchor="start", extra=""):
    """Monospace text where every character is exactly CW wide, like the header."""
    n = sum(len(t) for _, t in parts)
    inner = "".join(f'<tspan class="{k}">{t}</tspan>' for k, t in parts)
    return (f'<text class="info" x="{fnum(x)}" y="{fnum(y)}" text-anchor="{anchor}" textLength="{n * CW:.1f}" '
            f'lengthAdjust="spacing" xml:space="preserve" {extra}>{inner}</text>')


def decorate(path, logo_b64):
    svg = open(path, encoding="utf-8").read()
    if "data-decorated" in svg:
        print(f"{path}: already decorated")
        return
    m = re.search(r'<svg width="(\d+)" height="(\d+)"', svg)
    d = re.search(r'dur="(\d+)ms"', svg)
    events = parse_events(svg)
    if not (m and d and events):
        print(f"{path}: unexpected format, leaving it untouched")
        return
    GW = int(m.group(1))
    d_old = int(d.group(1))
    game = int(d_old * SPEED)
    d_new = game + int(EXTRA * 1000)
    sc = game / d_new

    svg, n_fixed = rescale(svg, d_old, d_new, sc)
    if n_fixed < 50:
        print(f"{path}: only {n_fixed} animations matched, leaving it untouched")
        return

    c = THEMES["dark" if "-dark" in os.path.basename(path) else "light"]

    # month labels: lift them out so they can be redrawn in the card's font
    months = [(float(x), name) for x, name in
              re.findall(r'<text x="([\d.]+)" y="10"[^>]*>([A-Za-z]*)</text>', svg) if name]
    svg = re.sub(r'<text x="[\d.]+" y="10"[^>]*>[A-Za-z]*</text>', "", svg)
    svg = re.sub(r'<rect width="100%" height="100%" fill="[^"]*"/>', "", svg, count=1)
    svg = re.sub(r'(<rect id="w[hv]-[^>]*fill=")[^"]*"', rf'\g<1>{c["wall"]}"', svg)
    if c["empty_from"] != c["empty"]:
        svg = svg.replace(c["empty_from"], c["empty"])

    # board: cells start at y=15 with a 22px pitch; walls sit 2px outside them
    vx, vy, vw, vh = -3, 12, GW + 4, 7 * 22 + 4
    s = (W - 2 * PAD) / vw
    bx, by = PAD, 66
    bh = vh * s
    svg = svg.replace(m.group(0), f'<svg x="{bx}" y="{by}" width="{W - 2 * PAD}" height="{bh:.1f}" '
                                  f'viewBox="{vx} {vy} {vw} {vh}"', 1)
    svg = svg[svg.index("<svg"):]

    hud_y = by + bh + 30
    H = int(hud_y + PAD + 2)
    dur = f"{d_new}ms"
    total = len(events)
    times = [t * sc for t, _, _ in events]          # fractions of the new loop

    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
         f'font-family="{FONT}" data-decorated="1">',
         "<title>Contribution Pac-Man</title>",
         "<style>",
         ".info{font-size:13.5px;white-space:pre}",
         f".text{{fill:{c['text']}}} .key{{fill:{c['key']}}} .val{{fill:{c['val']}}} .dots{{fill:{c['dots']}}}",
         "</style>",
         f'<rect width="{W}" height="{H}" rx="15" fill="{c["bg"]}" stroke="{c["border"]}"/>']
    title = "- Pac-Man: eating a year of contributions "
    o.append(text(PAD, PAD + 12, [("text", title), ("dots", "-" * (COLS - len(title)))]))

    next_x = W  # right to left, so a leading partial month gives way to the full one after it
    for x, name in reversed(months):
        ox = bx + (x - vx) * s - 1.5 * CW
        if next_x - ox >= 4 * CW and ox + 3 * CW <= W - PAD:
            o.append(text(max(PAD, ox), by - 8, [("dots", name[:3])]))
            next_x = ox

    o.append(svg)

    # boxes eaten: label, bar, counter on one line, like the tracker's progress row
    label = ". Boxes eaten: "
    count_w = len(f"{total} / {total}")
    o.append(text(PAD, hud_y, [("key", label.rstrip())]))
    x0 = PAD + len(label) * CW
    bw = (COLS - len(label) - count_w - 1) * CW
    o.append(f'<rect x="{fnum(x0)}" y="{fnum(hud_y - 8.5)}" width="{fnum(bw)}" height="9" rx="2" fill="{c["track"]}"/>')
    widths = [0] + [bw * (i + 1) / total for i in range(total)] + [bw]
    kts = [0.0] + times + [1.0]
    o.append(f'<rect x="{fnum(x0)}" y="{fnum(hud_y - 8.5)}" width="0" height="9" rx="2" fill="{c["bar"]}">'
             f'<animate attributeName="width" dur="{dur}" repeatCount="indefinite" '
             f'values="{";".join(fnum(w) for w in widths)}" keyTimes="{";".join(fnum(k) for k in kts)}"/></rect>')
    for k in range(total + 1):
        a = times[k - 1] if k > 0 else 0.0
        b = times[k] if k < total else 1.0
        if k == 0:
            vv, kk = "1;0;0", f"0;{fnum(b)};1"
        elif k == total:
            vv, kk = "0;1;1", f"0;{fnum(a)};1"
        else:
            vv, kk = "0;1;0;0", f"0;{fnum(a)};{fnum(b)};1"
        o.append(text(W - PAD, hud_y, [("val", f"{k} / {total}")], anchor="end",
                      extra=f'opacity="{1 if k == 0 else 0}"').replace(
            "</text>", f'<animate attributeName="opacity" calcMode="discrete" dur="{dur}" repeatCount="indefinite" '
                       f'values="{vv}" keyTimes="{kk}"/></text>'))

    # easter egg: appears once the last box is eaten, gone before the loop restarts
    G, T = game / 1000.0, d_new / 1000.0
    t_in, t_full, t_out, t_gone = G + 0.3, G + 0.9, T - 1.0, T - 0.4
    ek = [0, t_in / T, t_full / T, t_out / T, t_gone / T, 1]
    size = 96
    ey0, ey1 = by - 26, by + bh + 4
    cx, cy = W / 2, (ey0 + ey1) / 2 - 12
    msg = [("dots", "> "), ("key", "level clear"), ("dots", " . "), ("val", f"{total} / {total}"),
           ("text", " boxes eaten"), ("dots", " . restarting_")]
    o.append(f'<g opacity="0"><animate attributeName="opacity" dur="{dur}" repeatCount="indefinite" '
             f'values="0;0;1;1;0;0" keyTimes="{";".join(fnum(k) for k in ek)}"/>'
             f'<rect x="{PAD - 4}" y="{ey0}" width="{W - 2 * PAD + 8}" height="{fnum(ey1 - ey0)}" rx="6" fill="{c["bg"]}"/>'
             f'<image href="data:image/png;base64,{logo_b64}" x="{fnum(cx - size / 2)}" y="{fnum(cy - size / 2)}" '
             f'width="{size}" height="{size}"/>'
             + text(cx, cy + size / 2 + 22, msg, anchor="middle") + "</g>")
    o.append("</svg>")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(o) + "\n")
    print(f"{path}: {total} boxes, {n_fixed} animations rescaled, loop {d_old / 1000:.1f}s -> {T:.1f}s")


def main():
    folder = sys.argv[1] if len(sys.argv) > 1 else "dist"
    with open(os.path.join(HERE, "easter_egg.png"), "rb") as f:
        logo = base64.b64encode(f.read()).decode()
    found = False
    for name in sorted(os.listdir(folder)):
        if name.startswith("pacman-contribution-graph") and name.endswith(".svg"):
            found = True
            try:
                decorate(os.path.join(folder, name), logo)
            except Exception as e:  # never break the profile because of decoration
                print(f"{name}: could not decorate ({e}); left as is")
    if not found:
        print("no pacman svg found in", folder)


if __name__ == "__main__":
    main()
