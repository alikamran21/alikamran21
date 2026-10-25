"""Adds a real progress bar and an easter egg to the generated Pac-Man SVGs.

Usage: python decorate_pacman.py <dir containing pacman-contribution-graph*.svg>

The game file already says, for every contribution box, the exact moment it is
eaten (a fill animation on the box). This script:
  1. stretches the loop by EXTRA seconds, rescaling every animation so the game
     itself plays exactly as before,
  2. adds a "boxes eaten" bar and counter driven by those same eat times,
  3. shows the easter egg (easter_egg.png) once the board is clear, then the
     loop restarts the game.
If the file does not look the way this script expects, it is left untouched.
"""
import base64
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EXTRA = 8.0          # seconds added to the loop for the easter egg
BAR_SPACE = 34       # extra pixels of height for the bar

ANIM_TAG = re.compile(r"<(animate|animateTransform)\b[^>]*>", re.S)


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


def rescale(svg, d_old, d_new):
    sc = d_old / d_new
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

    return ANIM_TAG.sub(fix, svg), count, sc


def decorate(path, logo_b64):
    svg = open(path, encoding="utf-8").read()
    if "data-decorated" in svg:
        print(f"{path}: already decorated")
        return
    m = re.search(r"<svg width=\"(\d+)\" height=\"(\d+)\"", svg)
    d = re.search(r'dur="(\d+)ms"', svg)
    events = parse_events(svg)
    if not (m and d and events):
        print(f"{path}: unexpected format, leaving it untouched")
        return
    W, H = int(m.group(1)), int(m.group(2))
    d_old = int(d.group(1))
    d_new = d_old + int(EXTRA * 1000)

    svg, n_fixed, sc = rescale(svg, d_old, d_new)
    if n_fixed < 50:
        print(f"{path}: only {n_fixed} animations matched, leaving it untouched")
        return

    dark = "-dark" in os.path.basename(path)
    page = "#0d1117" if dark else "#ffffff"
    muted = "#8b949e" if dark else "#57606a"
    text = "#e6edf3" if dark else "#1f2328"
    track = "#21262d" if dark else "#d0d7de"
    bar = "#39d353" if dark else "#30a14e"
    font = "-apple-system, 'Segoe UI', Helvetica, Arial, sans-serif"

    total = len(events)
    times = [t * sc for t, _, _ in events]          # fractions of the new loop
    bw = W - 2 * 2 - 0
    x0 = 2
    label_y = H + 12
    bar_y = H + 18
    dur = f"{d_new}ms"

    o = ['<g data-decorated="1">']
    o.append(f'<text x="{x0}" y="{label_y}" font-size="11" fill="{muted}" font-family="{font}">Boxes eaten</text>')
    o.append(f'<rect x="{x0}" y="{bar_y}" width="{bw}" height="8" rx="4" fill="{track}"/>')
    widths = [0] + [bw * (i + 1) / total for i in range(total)] + [bw]
    kts = [0.0] + times + [1.0]
    o.append(f'<rect x="{x0}" y="{bar_y}" width="0" height="8" rx="4" fill="{bar}">'
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
        o.append(f'<text x="{x0 + bw}" y="{label_y}" font-size="11" font-weight="600" text-anchor="end" '
                 f'fill="{text}" font-family="{font}" opacity="{1 if k == 0 else 0}">{k} / {total}'
                 f'<animate attributeName="opacity" calcMode="discrete" dur="{dur}" repeatCount="indefinite" '
                 f'values="{vv}" keyTimes="{kk}"/></text>')

    # easter egg: appears once the last box is eaten, gone before the loop restarts
    D = d_old / 1000.0
    T = d_new / 1000.0
    t_in, t_full, t_out, t_gone = D + 0.3, D + 0.9, T - 1.0, T - 0.4
    ek = [0, t_in / T, t_full / T, t_out / T, t_gone / T, 1]
    size = 118
    gy0, gy1 = 12, H - 14
    cx, cy = W / 2, (gy0 + gy1) / 2 - 8
    o.append(f'<g id="egg" opacity="0"><animate attributeName="opacity" dur="{dur}" repeatCount="indefinite" '
             f'values="0;0;1;1;0;0" keyTimes="{";".join(fnum(k) for k in ek)}"/>'
             f'<rect x="0" y="{gy0}" width="{W}" height="{gy1 - gy0}" rx="6" fill="{page}" opacity="0.93"/>'
             f'<image href="data:image/png;base64,{logo_b64}" x="{cx - size / 2}" y="{cy - size / 2}" width="{size}" height="{size}"/>'
             f'<text x="{cx}" y="{gy1 - 4}" font-size="11" text-anchor="middle" fill="{muted}" font-family="{font}">'
             f'level clear · {total} boxes eaten · restarting</text></g>')
    o.append("</g>")

    svg = svg.replace(m.group(0), f'<svg width="{W}" height="{H + BAR_SPACE}"', 1)
    svg = svg[: svg.rindex("</svg>")] + "".join(o) + "</svg>"
    with open(path, "w", encoding="utf-8") as f:
        f.write(svg)
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
