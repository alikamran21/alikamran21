"""Draws the contribution Tetris game (tetris_dark.svg / tetris_light.svg).

The year's contribution graph is cut into tetrominoes (plus a few smaller
pieces where the shape forces it). Pieces spawn above the well, slide and
rotate into line like a player is steering them, then drop row by row and lock
into place, turning from their Tetris colour into the day's contribution green.
Pieces land in an order that is physically possible (nothing falls through a
block that is already there). When the graph is complete every row flashes and
clears from the centre out, NES style, then the game restarts.

Everything is driven from stats.json (the "calendar" key), so the dark and
light versions play the identical game, and it follows the header's terminal
look: same card, colours and monospace type.
"""
import datetime
import os
import random
from xml.sax.saxutils import escape

HERE = os.path.dirname(os.path.abspath(__file__))

# timing, in seconds
INPUT = 0.16          # per sideways move / rotation while steering a piece
DROP = 0.09           # per row of gravity
LOCK = 0.18           # pause after a piece locks
FLASH = 1.6           # board flash once the graph is complete
WIPE = 0.7            # rows clearing from the centre out
END = 6.0             # "TETRIS!" screen before the restart

THEMES = {
    "dark": dict(bg="#161b22", text="#c9d1d9", key="#ffa657", val="#a5d6ff", dots="#616e7f",
                 border="#30363d", track="#21262d", well="#0d1117", bar="#39d353",
                 levels=["#0e4429", "#006d32", "#26a641", "#39d353"],
                 pieces=dict(I="#39c5cf", O="#e3b341", T="#bc8cff", S="#3fb950", Z="#ff7b72",
                             J="#58a6ff", L="#ffa657", small="#f778ba")),
    "light": dict(bg="#f6f8fa", text="#24292f", key="#953800", val="#0a3069", dots="#a8b3c1",
                  border="#d0d7de", track="#dde3ea", well="#eef1f4", bar="#30a14e",
                  levels=["#9be9a8", "#40c463", "#30a14e", "#216e39"],
                  pieces=dict(I="#1b7c83", O="#9a6700", T="#8250df", S="#1a7f37", Z="#cf222e",
                              J="#0969da", L="#bc4c00", small="#bf3989")),
}
FONT = "Consolas, 'Liberation Mono', Menlo, 'DejaVu Sans Mono', monospace"
W = 1000
PAD = 20
CW = 8.0              # px per character, as in the header
LH = 19.5             # px per line
COLS = int((W - 2 * PAD) / CW)
SPAWN = 3             # rows of open well above the board

SHAPES = {
    "I": [(0, 0), (1, 0), (2, 0), (3, 0)],
    "O": [(0, 0), (1, 0), (0, 1), (1, 1)],
    "T": [(0, 0), (1, 0), (2, 0), (1, 1)],
    "S": [(1, 0), (2, 0), (0, 1), (1, 1)],
    "Z": [(0, 0), (1, 0), (1, 1), (2, 1)],
    "J": [(0, 0), (0, 1), (1, 1), (2, 1)],
    "L": [(2, 0), (0, 1), (1, 1), (2, 1)],
}


def fnum(x):
    s = f"{x:.5f}".rstrip("0").rstrip(".")
    return s or "0"


def norm(cells):
    mx, my = min(x for x, _ in cells), min(y for _, y in cells)
    return frozenset((x - mx, y - my) for x, y in cells)


def rotations(cells):
    out, cur = [], list(cells)
    for _ in range(4):
        out.append(norm(cur))
        cur = [(-y, x) for x, y in cur]
    return out


KINDS = {r: k for k, cells in SHAPES.items() for r in rotations(cells)}


def kind_of(cells):
    return KINDS.get(norm(cells), "small")


def tile(active):
    """Cut the active cells into pieces of up to 4 connected cells, preferring full tetrominoes."""
    left = set(active)
    pieces = []

    def free_nbrs(c):
        x, y = c
        return [n for n in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)) if n in left]

    for seed in sorted(active):
        if seed not in left:
            continue
        piece = [seed]
        left.discard(seed)
        while len(piece) < 4:
            options = {n for c in piece for n in free_nbrs(c)}
            if not options:
                break
            # take the neighbour with the fewest other free neighbours, so nothing gets stranded
            best = min(options, key=lambda n: (len(free_nbrs(n)), n))
            piece.append(best)
            left.discard(best)
        pieces.append(piece)
    return pieces


def drop_order(pieces):
    """Order the pieces so each one can fall straight down to its spot.

    A piece falling into column x passes every cell above its own in that column,
    so those cells must still be empty: the lower piece goes first. If two pieces
    block each other, they are split into single blocks (which never do)."""
    pieces = [list(p) for p in pieces]
    while True:
        owner = {c: i for i, p in enumerate(pieces) for c in p}
        after = {i: set() for i in range(len(pieces))}   # i must land before every j in after[i]
        for i, p in enumerate(pieces):
            for x, y in p:
                for yy in range(y):
                    j = owner.get((x, yy))
                    if j is not None and j != i:
                        after[i].add(j)
        need = {i: 0 for i in after}
        for i in after:
            for j in after[i]:
                need[j] += 1
        ready = [i for i in need if need[i] == 0]
        order = []
        while ready:
            ready.sort(key=lambda i: (min(x for x, _ in pieces[i]), -max(y for _, y in pieces[i])))
            i = ready.pop(0)
            order.append(i)
            for j in after[i]:
                need[j] -= 1
                if need[j] == 0:
                    ready.append(j)
        if len(order) == len(pieces):
            return [pieces[i] for i in order]
        stuck = [i for i in need if need[i] > 0]
        worst = max(stuck, key=lambda i: len(pieces[i]))
        pieces = [p for i, p in enumerate(pieces) if i != worst] + [[c] for c in pieces[worst]]


def text(x, y, parts, anchor="start", extra=""):
    """Monospace text where every character is exactly CW wide, like the header."""
    n = sum(len(t) for _, t in parts)
    inner = "".join(f'<tspan class="{k}">{escape(t)}</tspan>' for k, t in parts)
    return (f'<text class="info" x="{fnum(x)}" y="{fnum(y)}" text-anchor="{anchor}" textLength="{n * CW:.1f}" '
            f'lengthAdjust="spacing" xml:space="preserve" {extra}>{inner}</text>')


def render(theme, stats):
    c = THEMES[theme]
    cal = sorted((datetime.date.fromisoformat(d), n) for d, n in stats["calendar"])
    d0 = cal[0][0]
    first_row = (d0.weekday() + 1) % 7                 # columns are weeks starting on Sunday
    grid = {}
    for d, n in cal:
        grid[(((d - d0).days + first_row) // 7, (d.weekday() + 1) % 7)] = (d, n)
    ncols = max(x for x, _ in grid) + 1
    nz = sorted(n for _, n in grid.values() if n > 0)
    cuts = [nz[int(len(nz) * q) - 1] for q in (0.25, 0.5, 0.75)] if len(nz) >= 4 else [1, 2, 3]

    def level(n):
        return sum(n > k for k in cuts)

    rng = random.Random(d0.toordinal())               # same game in both themes, new one each year
    pieces = drop_order(tile([cell for cell, (_, n) in grid.items() if n > 0]))

    # ---- geometry
    p = (W - 2 * PAD) / ncols                          # cell pitch
    cs = p - 3                                         # cell size
    wt = 48                                            # top of the well
    by = wt + SPAWN * p                                # top of the board
    bb = by + 7 * p                                    # bottom of the board
    month_y = bb + 16
    hud_y = month_y + 26
    log_y = hud_y + LH
    H = int(log_y + PAD + 4)

    def cx(col):
        return PAD + col * p

    def cy(row):
        return by + row * p

    # ---- timeline: steer, drop, lock, next piece
    plan, t = [], 0.6
    for cells in pieces:
        xs = [x for x, _ in cells]
        ys = [y for _, y in cells]
        w_, h_ = max(xs) - min(xs) + 1, max(ys) - min(ys) + 1
        shift = rng.randint(-3, 3)
        shift = max(-min(xs), min(ncols - 1 - max(xs), shift))
        turns = rng.choice([0, 1, 1, 2, 3]) if max(w_, h_) <= 3 and len(cells) > 1 else 0
        lift = max(ys) + 1                             # rows up to sit just above the board
        moves = [("turn",)] * turns + [("shift",)] * abs(shift)
        rng.shuffle(moves)
        frames = [(t, shift, -lift, turns * 90)]       # (time, dx cols, dy rows, rotation)
        dx, rot = shift, turns * 90
        for mv in moves:
            t += INPUT
            if mv[0] == "turn":
                rot = (rot + 90) % 360
            else:
                dx -= 1 if dx > 0 else -1
            frames.append((t, dx, -lift, rot))
        for r in range(lift - 1, -1, -1):
            t += DROP
            frames.append((t, 0, -r, 0))
        land = t
        t += LOCK
        plan.append(dict(cells=cells, kind=kind_of(cells), frames=frames, spawn=frames[0][0], land=land,
                         n=sum(grid[cell][1] for cell in cells), days=sorted(grid[cell][0] for cell in cells),
                         centre=(cx(min(xs)) + w_ * p / 2, cy(min(ys)) + h_ * p / 2)))
    done = t + 0.4
    flash_end = done + FLASH
    wipe_end = flash_end + WIPE
    T = wipe_end + END
    dur = f"{T:.2f}s"
    total = len(plan)

    def fr(x):
        return min(1.0, max(0.0, x / T))

    def shown(a, b, initially=False):
        """display animation: in the render tree only from a to b seconds into the loop."""
        vals, kts = (["inline"] if a <= 0 else ["none", "inline"]), ([0] if a <= 0 else [0, fr(a)])
        if b < T:
            vals.append("none")
            kts.append(fr(b))
        return (f'<animate attributeName="display" calcMode="discrete" dur="{dur}" repeatCount="indefinite" '
                f'values="{";".join(vals)}" keyTimes="{";".join(fnum(k) for k in kts)}"/>')

    def hidden(a):
        return "" if a <= 0 else 'display="none"'

    o = ['<?xml version="1.0" encoding="UTF-8"?>',
         f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="{FONT}">',
         "<title>Contribution Tetris</title>",
         "<style>",
         ".info{font-size:13.5px;white-space:pre}",
         f".text{{fill:{c['text']}}} .key{{fill:{c['key']}}} .val{{fill:{c['val']}}} .dots{{fill:{c['dots']}}}",
         "</style>",
         f'<defs><clipPath id="well"><rect x="{PAD - 2}" y="{wt}" width="{W - 2 * PAD + 4}" height="{fnum(bb - wt + 2)}"/></clipPath></defs>',
         f'<rect width="{W}" height="{H}" rx="15" fill="{c["bg"]}" stroke="{c["border"]}"/>']

    title = "- Tetris: stacking a year of contributions "
    nxt = "next: "
    o.append(text(PAD, PAD + 12, [("text", title), ("dots", "-" * (COLS - len(title) - len(nxt) - 7) + " "),
                                  ("key", nxt.strip())]))

    # well and empty board
    o.append(f'<rect x="{PAD - 2}" y="{wt}" width="{W - 2 * PAD + 4}" height="{fnum(bb - wt + 2)}" rx="4" fill="{c["well"]}"/>')
    for (col, row) in grid:
        o.append(f'<rect x="{fnum(cx(col))}" y="{fnum(cy(row))}" width="{fnum(cs)}" height="{fnum(cs)}" rx="3" fill="{c["track"]}"/>')

    # month labels under the board (right to left, so a leading partial month gives way)
    marks, last = [], None
    for col in range(ncols):
        d = min((grid[(col, r)][0] for r in range(7) if (col, r) in grid), default=None)
        if d and d.month != last:
            marks.append((col, d.strftime("%b")))
            last = d.month
    next_x = W
    for col, name in reversed(marks):
        x = cx(col)
        if next_x - x >= 4 * CW and x + 3 * CW <= W - PAD:
            o.append(text(x, month_y, [("dots", name)]))
            next_x = x

    def block(x, y, fill, shine=True):
        out = f'<rect x="{fnum(x)}" y="{fnum(y)}" width="{fnum(cs)}" height="{fnum(cs)}" rx="3" fill="{fill}"/>'
        if shine:
            out += (f'<rect x="{fnum(x + 2)}" y="{fnum(y + 2)}" width="{fnum(cs - 4)}" height="{fnum(cs / 3)}" rx="1.5" '
                    f'fill="#fff" opacity=".22"/>')
        return out

    # landed blocks in contribution green: one group per piece, shown from the moment it locks
    for pc in plan:
        body = "".join(block(cx(x), cy(y), c["levels"][level(grid[(x, y)][1])], shine=False) for x, y in pc["cells"])
        o.append(f'<g display="none">{shown(pc["land"], T)}{body}</g>')

    # falling pieces in Tetris colours, inside the well
    o.append('<g clip-path="url(#well)">')
    for pc in plan:
        fill = c["pieces"][pc["kind"]]
        body = "".join(block(cx(x), cy(y), fill) for x, y in pc["cells"])
        kt = [0] + [fr(f[0]) for f in pc["frames"]]
        moves = [pc["frames"][0]] + pc["frames"]
        trans = ";".join(f"{fnum(f[1] * p)},{fnum(f[2] * p)}" for f in moves)
        ox, oy = pc["centre"]
        rots = ";".join(f"{f[3]} {fnum(ox)} {fnum(oy)}" for f in moves)
        anims = (f'<animateTransform attributeName="transform" type="translate" calcMode="discrete" dur="{dur}" '
                 f'repeatCount="indefinite" values="{trans}" keyTimes="{";".join(fnum(k) for k in kt)}"/>')
        spin = ""
        if any(f[3] for f in pc["frames"]):
            spin = (f'<animateTransform attributeName="transform" type="rotate" calcMode="discrete" dur="{dur}" '
                    f'repeatCount="indefinite" values="{rots}" keyTimes="{";".join(fnum(k) for k in kt)}"/>')
        o.append(f'<g {hidden(pc["spawn"])}>{shown(pc["spawn"], pc["land"])}{anims}<g>{spin}{body}</g></g>')
    o.append("</g>")

    # NEXT preview in the title row
    px0 = W - PAD - 6 * CW
    mini = 7
    for i, pc in enumerate(plan):
        a = plan[i - 1]["spawn"] if i else 0
        cells = sorted(norm(pc["cells"]))
        w_ = max(x for x, _ in cells) + 1
        h_ = max(y for _, y in cells) + 1
        x0 = px0 + (6 * CW - w_ * mini) / 2
        y0 = PAD + 7 - h_ * mini / 2
        body = "".join(f'<rect x="{fnum(x0 + x * mini)}" y="{fnum(y0 + y * mini)}" width="{mini - 1}" height="{mini - 1}" '
                       f'rx="1" fill="{c["pieces"][pc["kind"]]}"/>' for x, y in cells)
        o.append(f'<g {hidden(a)}>{shown(a, pc["spawn"])}{body}</g>')

    # HUD: pieces bar + counter, then a drop log line with the running score
    label = ". Pieces: "
    count_w = len(f"{total} / {total}")
    o.append(text(PAD, hud_y, [("key", label.rstrip())]))
    x0 = PAD + len(label) * CW
    bw = (COLS - len(label) - count_w - 1) * CW
    o.append(f'<rect x="{fnum(x0)}" y="{fnum(hud_y - 8.5)}" width="{fnum(bw)}" height="9" rx="2" fill="{c["track"]}"/>')
    widths = [0] + [bw * (i + 1) / total for i in range(total)] + [bw]
    kts = [0] + [fr(pc["land"]) for pc in plan] + [1]
    o.append(f'<rect x="{fnum(x0)}" y="{fnum(hud_y - 8.5)}" width="0" height="9" rx="2" fill="{c["bar"]}">'
             f'<animate attributeName="width" calcMode="discrete" dur="{dur}" repeatCount="indefinite" '
             f'values="{";".join(fnum(w) for w in widths)}" keyTimes="{";".join(fnum(k) for k in kts)}"/></rect>')

    score = 0
    starts = [0] + [pc["land"] for pc in plan]
    for k in range(total + 1):
        a, b = starts[k], (starts[k + 1] if k < total else T)
        o.append(text(W - PAD, hud_y, [("val", f"{k} / {total}")], anchor="end", extra=hidden(a))
                 .replace("</text>", shown(a, b) + "</text>"))
        if k == 0:
            left = [("dots", "> "), ("text", "insert coin...")]
        else:
            pc = plan[k - 1]
            score += pc["n"]
            d1, d2 = pc["days"][0], pc["days"][-1]
            when = f"{d1:%b} {d1.day}" + (f" - {d2:%b} {d2.day}" if d2 != d1 else "")
            name = f"{pc['kind']}-piece" if pc["kind"] != "small" else f"{len(pc['cells'])}-block"
            left = [("dots", "> "), ("key", "drop"), ("dots", " . "), ("text", name), ("dots", " . "),
                    ("text", when), ("dots", " . "), ("val", f"+{pc['n']:,}")]
        right = [("key", "Score:"), ("val", f" {score:,}")]
        used = sum(len(x) for _, x in left + right)
        parts = left + [("dots", " " + "." * max(2, COLS - used - 2) + " ")] + right
        o.append(text(PAD, log_y, parts, extra=hidden(a)).replace("</text>", shown(a, b) + "</text>"))

    # finale: the whole board flashes, then every row clears from the centre out
    span = W - 2 * PAD + 4
    blink = ";".join(["0", ".55", "0", ".55", "0", ".55", "0"])
    bk = ";".join(fnum(fr(done + FLASH * i / 6)) for i in range(7))
    o.append(f'<rect x="{PAD - 2}" y="{fnum(by - 2)}" width="{span}" height="{fnum(7 * p + 2)}" rx="4" fill="#fff" opacity="0">'
             f'<animate attributeName="opacity" dur="{dur}" repeatCount="indefinite" values="0;{blink};0" '
             f'keyTimes="0;{bk};1"/></rect>')
    steps = 5
    wx = ";".join(fnum(W / 2 - span / 2 * i / steps) for i in range(steps + 1))
    ww = ";".join(fnum(span * i / steps) for i in range(steps + 1))
    wk = ";".join(fnum(fr(flash_end + WIPE * i / steps)) for i in range(steps + 1))
    o.append(f'<rect x="{W / 2}" y="{fnum(by - 2)}" width="0" height="{fnum(7 * p + 3)}" fill="{c["well"]}">'
             f'<animate attributeName="x" calcMode="discrete" dur="{dur}" repeatCount="indefinite" values="{W / 2};{wx}" keyTimes="0;{wk}"/>'
             f'<animate attributeName="width" calcMode="discrete" dur="{dur}" repeatCount="indefinite" values="0;{ww}" keyTimes="0;{wk}"/></rect>')

    # TETRIS! screen with the coffeebean easter egg
    logo = os.path.join(HERE, "easter_egg.png")
    img = ""
    if os.path.exists(logo):
        import base64
        with open(logo, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        img = f'<image href="data:image/png;base64,{b64}" x="{fnum(PAD + 40)}" y="{fnum(wt + 8)}" width="{fnum(bb - wt - 16)}" height="{fnum(bb - wt - 16)}"/>'
    mid = (wt + bb) / 2
    msg = [("dots", "> "), ("key", "year stacked"), ("dots", " . "), ("val", f"{total}"), ("text", " pieces"),
           ("dots", " . "), ("val", f"{score:,}"), ("text", " contributions"), ("dots", " . restarting_")]
    o.append(f'<g display="none">{shown(wipe_end, T - 0.3)}{img}'
             f'<text x="{W / 2}" y="{fnum(mid + 4)}" text-anchor="middle" font-size="44" font-weight="700" '
             f'letter-spacing="14" fill="{c["key"]}">TETRIS!</text>'
             + text(W / 2, mid + 34, msg, anchor="middle") + "</g>")

    o.append("</svg>")
    return "\n".join(o) + "\n", T, total


def build(stats):
    if not stats.get("calendar"):
        print("no calendar data yet; skipping tetris")
        return
    for theme in ("dark", "light"):
        svg, T, total = render(theme, stats)
        with open(os.path.join(HERE, f"tetris_{theme}.svg"), "w", encoding="utf-8") as f:
            f.write(svg)
    print(f"wrote tetris_dark.svg and tetris_light.svg ({total} pieces, {T:.0f}s loop)")
