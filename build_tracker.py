"""Draws the contribution tracker (tracker_dark.svg / tracker_light.svg).

Data comes from the same stats.json that build_header.py maintains. The
"calendar" key holds [[YYYY-MM-DD, count], ...] for the last year.
"""
import datetime
import os
from xml.sax.saxutils import escape

HERE = os.path.dirname(os.path.abspath(__file__))

# How long (seconds) one loop of the "boxes eaten" bar takes. The bar is its own
# animation, so set this to roughly the length of your Pac-Man game to keep them in step.
PACMAN_SECONDS = 30
FRAMES = 24

THEMES = {
    "dark": dict(bg="#161b22", tile="#0d1117", border="#30363d", text="#c9d1d9",
                 muted="#8b949e", accent="#39d353", accent2="#0e4429", pac="#facc15"),
    "light": dict(bg="#f6f8fa", tile="#ffffff", border="#d0d7de", text="#24292f",
                  muted="#57606a", accent="#216e39", accent2="#aceebb", pac="#ca8a04"),
}
FALLBACK_COLORS = ["#58a6ff", "#f78166", "#d2a8ff", "#3fb950", "#e3b341", "#79c0ff"]

CALENDAR_QUERY = """
query($login:String!){ user(login:$login){ contributionsCollection{
  totalCommitContributions restrictedContributionsCount
  contributionCalendar{ totalContributions weeks{ contributionDays{ date contributionCount } } }
}}}"""

EXTRA_QUERY = """
query($login:String!){ user(login:$login){
  createdAt
  pullRequests{ totalCount }
  issues{ totalCount }
  repositories(ownerAffiliations:OWNER, isFork:false, first:100){ nodes{
    languages(first:10, orderBy:{field:SIZE, direction:DESC}){ edges{ size node{ name color } } }
  }}
  contributionsCollection{ commitContributionsByRepository(maxRepositories:100){ repository{ nameWithOwner } } }
}}"""


def fetch_calendar(gql, token, user):
    cc = gql(token, CALENDAR_QUERY, {"login": user})["user"]["contributionsCollection"]
    days = [[d["date"], d["contributionCount"]]
            for w in cc["contributionCalendar"]["weeks"] for d in w["contributionDays"]]
    out = {
        "calendar": days,
        "year_total": cc["contributionCalendar"]["totalContributions"],
        "year_commits": cc["totalCommitContributions"] + cc["restrictedContributionsCount"],
    }
    try:
        out.update(fetch_extra(gql, token, user))
    except Exception as e:  # the core tracker still works without these extras
        print("could not fetch extra tracker stats:", e)
    return out


def fetch_extra(gql, token, user):
    u = gql(token, EXTRA_QUERY, {"login": user})["user"]
    langs = {}
    for repo in u["repositories"]["nodes"]:
        for e in repo["languages"]["edges"]:
            name = e["node"]["name"]
            cur = langs.setdefault(name, [name, e["node"]["color"], 0])
            cur[2] += e["size"]
    top = sorted(langs.values(), key=lambda x: -x[2])[:6]

    # all-time total, one year at a time
    start = int(u["createdAt"][:4])
    parts = [f'y{y}: contributionsCollection(from:"{y}-01-01T00:00:00Z", to:"{y}-12-31T23:59:59Z")'
             f'{{ contributionCalendar{{ totalContributions }} }}'
             for y in range(start, datetime.date.today().year + 1)]
    yrs = gql(token, "query($login:String!){ user(login:$login){ " + " ".join(parts) + " }}",
              {"login": user})["user"]
    return {
        "joined": u["createdAt"][:10],
        "all_time_total": sum(v["contributionCalendar"]["totalContributions"] for v in yrs.values()),
        "prs": u["pullRequests"]["totalCount"],
        "issues": u["issues"]["totalCount"],
        "languages": top,
        "contributed_repos": len(u["contributionsCollection"]["commitContributionsByRepository"]),
    }


def _date(s):
    return datetime.date.fromisoformat(s)


def short(d):
    return d.strftime("%b ") + str(d.day)


def analyse(calendar):
    days = sorted((_date(d), c) for d, c in calendar)
    today = datetime.date.today()
    days = [(d, c) for d, c in days if d <= today] or days

    longest, run, run_start, best_range = 0, 0, None, None
    for d, c in days:
        if c > 0:
            if run == 0:
                run_start = d
            run += 1
            if run > longest:
                longest, best_range = run, (run_start, d)
        else:
            run = 0

    cur, cur_end, cur_start = 0, None, None
    i = len(days) - 1
    if i >= 0 and days[i][1] == 0:  # today still empty: the streak is not broken yet
        i -= 1
    while i >= 0 and days[i][1] > 0:
        cur_end = cur_end or days[i][0]
        cur_start = days[i][0]
        cur += 1
        i -= 1

    best = max(days, key=lambda x: x[1])
    months = {}
    for d, c in days:
        months[(d.year, d.month)] = months.get((d.year, d.month), 0) + c
    keys = sorted(months)[-12:]
    return dict(total=sum(c for _, c in days), current=cur,
                current_range=(cur_start, cur_end) if cur else None,
                longest=longest, longest_range=best_range, best_day=best,
                months=[(k, months[k]) for k in keys],
                active_days=sum(1 for _, c in days if c > 0))


def fmt(n):
    return f"{n:,}" if isinstance(n, int) else str(n)


def rng(r):
    return f"{short(r[0])} - {short(r[1])}" if r else "-"


def pac_progress(c, total, x, y, w, animated):
    """Loading bar that fills as Pac-Man 'eats' the boxes, with a live counter."""
    D = PACMAN_SECONDS
    hold = 0.9  # the bar finishes at 90% of the loop and holds for the rest
    o = [f'<text x="{x}" y="{y}" font-size="12" fill="{c["muted"]}">Pac-Man progress</text>',
         f'<text x="{x + w}" y="{y}" font-size="12" text-anchor="end" fill="{c["muted"]}">boxes eaten</text>']
    by, bh = y + 12, 16
    o.append(f'<rect x="{x}" y="{by}" width="{w}" height="{bh}" rx="8" fill="{c["tile"]}" stroke="{c["border"]}"/>')
    # pellets along the track
    for i in range(1, 40):
        px = x + 14 + (w - 28) * i / 40
        o.append(f'<circle cx="{px:.1f}" cy="{by + bh / 2}" r="1.6" fill="{c["muted"]}" opacity="0.35"/>')

    if animated:
        o.append(f'<rect x="{x}" y="{by}" width="0" height="{bh}" rx="8" fill="{c["accent"]}" opacity="0.9">'
                 f'<animate attributeName="width" values="0;{w};{w}" keyTimes="0;{hold};1" dur="{D}s" repeatCount="indefinite"/></rect>')
        o.append(f'<g transform="translate({x},{by + bh / 2})">'
                 f'<animateTransform attributeName="transform" type="translate" '
                 f'values="{x},{by + bh / 2};{x + w - 8},{by + bh / 2};{x + w - 8},{by + bh / 2}" '
                 f'keyTimes="0;{hold};1" dur="{D}s" repeatCount="indefinite"/>'
                 f'<circle r="11" fill="{c["pac"]}"/>'
                 f'<polygon points="0,0 12,-7 12,7" fill="{c["bg"]}">'
                 f'<animate attributeName="points" values="0,0 12,-7 12,7;0,0 12,-1 12,1;0,0 12,-7 12,7" dur="0.5s" repeatCount="indefinite"/></polygon>'
                 f'<circle cx="2" cy="-5" r="1.6" fill="{c["bg"]}"/></g>')
        # counter frames
        for k in range(FRAMES):
            val = round(total * k / (FRAMES - 1))
            t0, t1 = hold * k / FRAMES, hold * (k + 1) / FRAMES
            if k == 0:
                vals, keys = "1;0;0", f"0;{t1:.4f};1"
            elif k == FRAMES - 1:
                vals, keys = "0;1;1", f"0;{t0:.4f};1"
            else:
                vals, keys = "0;1;0;0", f"0;{t0:.4f};{t1:.4f};1"
            op = "1" if k == 0 else "0"
            o.append(f'<text x="{x + w - 80}" y="{y}" font-size="12" font-weight="bold" text-anchor="end" '
                     f'fill="{c["accent"]}" opacity="{op}">{fmt(val)} / {fmt(total)}'
                     f'<animate attributeName="opacity" calcMode="discrete" values="{vals}" keyTimes="{keys}" '
                     f'dur="{D}s" repeatCount="indefinite"/></text>')
    else:  # static preview
        o.append(f'<rect x="{x}" y="{by}" width="{w}" height="{bh}" rx="8" fill="{c["accent"]}" opacity="0.9"/>')
        o.append(f'<text x="{x + w - 80}" y="{y}" font-size="12" font-weight="bold" text-anchor="end" '
                 f'fill="{c["accent"]}">{fmt(total)} / {fmt(total)}</text>')
    return o


def render(theme, stats, animated=True):
    c = THEMES[theme]
    a = analyse(stats["calendar"])
    year_total = stats.get("year_total", a["total"])
    W, H = 1000, 568
    font = "Consolas, 'Liberation Mono', Menlo, 'DejaVu Sans Mono', monospace"
    o = [f'<?xml version="1.0" encoding="UTF-8"?>',
         f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="{font}">',
         "<title>Contribution tracker</title>",
         f'<rect width="{W}" height="{H}" rx="15" fill="{c["bg"]}" stroke="{c["border"]}"/>',
         f'<text x="24" y="34" font-size="15" font-weight="bold" fill="{c["text"]}">Contribution tracker</text>']

    # Pac-Man progress
    o += pac_progress(c, a["active_days"], 24, 62, W - 48, animated)

    # three big tiles
    all_time = stats.get("all_time_total", year_total)
    joined = stats.get("joined")
    since = (_date(joined).strftime("%b ") + f"{_date(joined).day}, {_date(joined).year} - Present") if joined \
        else f"{fmt(a['active_days'])} active days (last year)"
    tiles = [
        ("Total contributions", fmt(all_time), since),
        ("Current streak", f"{a['current']} days", rng(a["current_range"])),
        ("Longest streak", f"{a['longest']} days", rng(a["longest_range"])),
    ]
    gap, x0, y0, th = 12, 24, 112, 92
    tw = (W - 48 - gap * 2) / 3
    for i, (label, big, sub) in enumerate(tiles):
        x = x0 + i * (tw + gap)
        o.append(f'<rect x="{x:.1f}" y="{y0}" width="{tw:.1f}" height="{th}" rx="10" fill="{c["tile"]}" stroke="{c["border"]}"/>')
        o.append(f'<text x="{x + 18:.1f}" y="{y0 + 26}" font-size="12" fill="{c["muted"]}">{escape(label)}</text>')
        o.append(f'<text x="{x + 18:.1f}" y="{y0 + 61}" font-size="30" font-weight="bold" fill="{c["accent"]}">{escape(big)}</text>')
        o.append(f'<text x="{x + 18:.1f}" y="{y0 + 80}" font-size="11" fill="{c["muted"]}">{escape(sub)}</text>')

    # stats panel (left) and languages panel (right)
    py, ph = 220, 152
    lw = 464
    o.append(f'<rect x="24" y="{py}" width="{lw}" height="{ph}" rx="10" fill="{c["tile"]}" stroke="{c["border"]}"/>')
    o.append(f'<text x="42" y="{py + 28}" font-size="13" font-weight="bold" fill="{c["text"]}">GitHub stats</text>')
    rows = [("Total stars earned", fmt(stats.get("stars", 0))),
            ("Commits (last year)", fmt(stats.get("year_commits", "n/a"))),
            ("Total PRs", fmt(stats.get("prs", "n/a"))),
            ("Total issues", fmt(stats.get("issues", "n/a"))),
            ("Contributed to (last year)", fmt(stats.get("contributed_repos", stats.get("contributed", "n/a"))))]
    for i, (k, v) in enumerate(rows):
        yy = py + 54 + i * 21
        o.append(f'<text x="42" y="{yy}" font-size="12" fill="{c["muted"]}">{escape(k)}</text>')
        o.append(f'<text x="{24 + lw - 18}" y="{yy}" font-size="12" font-weight="bold" text-anchor="end" fill="{c["accent"]}">{escape(v)}</text>')

    rx0 = 24 + lw + 12
    rw = W - 24 - rx0
    o.append(f'<rect x="{rx0}" y="{py}" width="{rw}" height="{ph}" rx="10" fill="{c["tile"]}" stroke="{c["border"]}"/>')
    o.append(f'<text x="{rx0 + 18}" y="{py + 28}" font-size="13" font-weight="bold" fill="{c["text"]}">Most used languages</text>')
    langs = stats.get("languages") or []
    if langs:
        tot = sum(l[2] for l in langs) or 1
        bx, by2, bw = rx0 + 18, py + 42, rw - 36
        o.append(f'<clipPath id="lc-{theme}"><rect x="{bx}" y="{by2}" width="{bw}" height="10" rx="5"/></clipPath>')
        cx = bx
        for i, (name, col, size) in enumerate(langs):
            seg = bw * size / tot
            o.append(f'<rect x="{cx:.1f}" y="{by2}" width="{seg + 0.5:.1f}" height="10" fill="{col or FALLBACK_COLORS[i % 6]}" clip-path="url(#lc-{theme})"/>')
            cx += seg
        for i, (name, col, size) in enumerate(langs):
            colx = bx + (i % 2) * (bw / 2)
            yy = py + 82 + (i // 2) * 24
            o.append(f'<circle cx="{colx + 5:.1f}" cy="{yy - 4}" r="5" fill="{col or FALLBACK_COLORS[i % 6]}"/>')
            o.append(f'<text x="{colx + 18:.1f}" y="{yy}" font-size="12" fill="{c["text"]}">{escape(name)} {100 * size / tot:.1f}%</text>')
    else:
        o.append(f'<text x="{rx0 + 18}" y="{py + 70}" font-size="12" fill="{c["muted"]}">Appears after the next stats run</text>')

    # monthly bars
    cx, cy, cw, ch = 24, 396, W - 48, 150
    o.append(f'<text x="{cx}" y="{cy}" font-size="12" fill="{c["muted"]}">Contributions per month (last 12 months)</text>')
    months = a["months"]
    peak = max(v for _, v in months) or 1
    slot = cw / len(months)
    bw2 = slot * 0.56
    base = cy + ch
    for i, ((yr, mo), v) in enumerate(months):
        bh = max(3, (v / peak) * (ch - 50)) if v else 3
        x = cx + i * slot + (slot - bw2) / 2
        op = 1 if v == peak else (0.35 if v == 0 else 0.55 + 0.45 * v / peak)
        label = datetime.date(yr, mo, 1).strftime("%b")
        o.append(f'<rect x="{x:.1f}" y="{base - bh - 22:.1f}" width="{bw2:.1f}" height="{bh:.1f}" rx="4" fill="{c["accent"]}" opacity="{op:.2f}"/>')
        o.append(f'<text x="{x + bw2 / 2:.1f}" y="{base - bh - 28:.1f}" font-size="11" text-anchor="middle" fill="{c["text"]}">{fmt(v)}</text>')
        o.append(f'<text x="{x + bw2 / 2:.1f}" y="{base - 6}" font-size="11" text-anchor="middle" fill="{c["muted"]}">{label}</text>')

    o.append("</svg>")
    return "\n".join(o) + "\n"


def build(stats):
    if not stats.get("calendar"):
        print("no calendar data yet; skipping tracker")
        return
    for theme in ("dark", "light"):
        with open(os.path.join(HERE, f"tracker_{theme}.svg"), "w") as f:
            f.write(render(theme, stats))
    print("wrote tracker_dark.svg and tracker_light.svg")
