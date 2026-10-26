"""Draws the contribution tracker (tracker_dark.svg / tracker_light.svg).

Data comes from the same stats.json that build_header.py maintains. The
"calendar" key holds [[YYYY-MM-DD, count], ...] for the last year.
"""
import datetime
import os
from xml.sax.saxutils import escape

HERE = os.path.dirname(os.path.abspath(__file__))

# same palette and type as the header card (build_header.py), plus contribution greens
THEMES = {
    "dark": dict(bg="#161b22", text="#c9d1d9", key="#ffa657", val="#a5d6ff", dots="#616e7f",
                 border="#30363d", track="#21262d", levels=["#0e4429", "#006d32", "#26a641", "#39d353"]),
    "light": dict(bg="#f6f8fa", text="#24292f", key="#953800", val="#0a3069", dots="#a8b3c1",
                  border="#d0d7de", track="#e1e4e8", levels=["#9be9a8", "#40c463", "#30a14e", "#216e39"]),
}
FONT = "Consolas, 'Liberation Mono', Menlo, 'DejaVu Sans Mono', monospace"
FALLBACK_COLORS = ["#58a6ff", "#f78166", "#d2a8ff", "#3fb950", "#e3b341", "#79c0ff"]
# neofetch's colour strip: normal and bright rows
PALETTE = [["#da3633", "#db6d28", "#d29922", "#238636", "#1b7c83", "#1f6feb", "#8957e5", "#6e7681"],
           ["#ff7b72", "#ffa657", "#e3b341", "#3fb950", "#39c5cf", "#58a6ff", "#bc8cff", "#b1bac4"]]

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

    return dict(total=sum(c for _, c in days), days=len(days), current=cur,
                current_range=(cur_start, cur_end) if cur else None,
                longest=longest, longest_range=best_range, best_day=max(days, key=lambda x: x[1]),
                active_days=sum(1 for _, c in days if c > 0))


def fmt(n):
    return f"{n:,}" if isinstance(n, int) else str(n)


def rng(r):
    return f"{short(r[0])} - {short(r[1])}" if r else "-"


WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

# ---------------------------------------------------------------- layout (matches build_header.py)
W = 1000
PAD = 20
CW = 8.0              # px per character
LH = 19.5             # px per line
FS = 13.5
LX, LCOLS = PAD, 56   # left column
RX, RCOLS = 548, 54   # right column, same x as the header's info column


def hdr(title, cols):
    text = f"- {title} "
    return [("text", text), ("dots", "-" * (cols - len(text)))]


def kv(key, val, cols, lead=". "):
    head = f"{lead}{key}:"
    dots = max(2, cols - len(head) - len(val) - 2)
    return [("key", head), ("dots", " " + "." * dots + " "), ("val", val)]


def render(theme, stats):
    c = THEMES[theme]
    a = analyse(stats["calendar"])
    cal = sorted((_date(d), n) for d, n in stats["calendar"])
    weeks = {}
    for d, n in cal:
        start = d - datetime.timedelta(days=(d.weekday() + 1) % 7)  # weeks start on Sunday
        weeks[start] = weeks.get(start, 0) + n
    wk = sorted(weeks.items())
    wd = [0] * 7
    for d, n in cal:
        wd[d.weekday()] += n

    rows = 20
    H = int(PAD * 2 + rows * LH - 12)
    o = ['<?xml version="1.0" encoding="UTF-8"?>',
         f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="{FONT}">',
         "<title>Contribution tracker</title>",
         "<style>",
         f".info{{font-size:{FS}px;white-space:pre}}",
         f".text{{fill:{c['text']}}} .key{{fill:{c['key']}}} .val{{fill:{c['val']}}} .dots{{fill:{c['dots']}}}",
         "</style>",
         f'<rect width="{W}" height="{H}" rx="15" fill="{c["bg"]}" stroke="{c["border"]}"/>']

    def base(row):
        return PAD + 12 + row * LH

    def line(x, row, parts, col=0):
        """One line of text; every character is exactly CW wide, like the header."""
        n = sum(len(t) for _, t in parts)
        inner = "".join(f'<tspan fill="{k}">{escape(t)}</tspan>' if k.startswith("#")
                        else f'<tspan class="{k}">{escape(t)}</tspan>' for k, t in parts)
        o.append(f'<text class="info" x="{x + col * CW:.1f}" y="{base(row):.1f}" textLength="{n * CW:.1f}" '
                 f'lengthAdjust="spacing" xml:space="preserve">{inner}</text>')

    def bar(x, row, col, width, fill, h=9):
        """A bar sitting on the text line, `col` characters in, `width` px long."""
        o.append(f'<rect x="{x + col * CW:.1f}" y="{base(row) - h + 0.5:.1f}" width="{max(0, width):.1f}" '
                 f'height="{h}" rx="2" fill="{fill}"/>')

    # ---------------- left column
    all_time = stats.get("all_time_total", stats.get("year_total", a["total"]))
    joined = stats.get("joined")
    since = f"{_date(joined).strftime('%b')} {_date(joined).day}, {_date(joined).year}" if joined else "-"
    best_d, best_n = a["best_day"]
    left = [
        hdr("Contributions", LCOLS),
        kv("Total", fmt(all_time), LCOLS),
        kv("Since", since, LCOLS),
        kv("Last 12 months", fmt(stats.get("year_total", a["total"])), LCOLS),
        kv("Active days", f"{a['active_days']} / {a['days']}", LCOLS),
        kv("Best day", f"{fmt(best_n)} {{{short(best_d)}}}", LCOLS),
        [("dots", ".")],
        hdr("Streaks", LCOLS),
        kv("Current", f"{a['current']} days {{{rng(a['current_range'])}}}", LCOLS),
        kv("Longest", f"{a['longest']} days {{{rng(a['longest_range'])}}}", LCOLS),
        None,  # current streak as a share of the longest, drawn below
        [("dots", ".")],
        hdr("By weekday", LCOLS),
    ]
    for i, parts in enumerate(left):
        if parts:
            line(LX, i, parts)

    label = ". Progress: "
    share = a["current"] / a["longest"] if a["longest"] else 0
    pct = f"{100 * share:.0f}%"
    line(LX, 10, [("key", label.rstrip())])
    track_w = (LCOLS - len(label) - len(pct) - 1) * CW
    bar(LX, 10, len(label), track_w, c["track"])
    bar(LX, 10, len(label), track_w * share, c["key"])
    line(LX, 10, [("val", pct)], col=LCOLS - len(pct))

    wmax = max(wd) or 1
    full = (LCOLS - 6 - 7) * CW
    for i, (nm, v) in enumerate(zip(WEEKDAYS, wd)):
        row = 13 + i
        val = fmt(v)
        line(LX, row, [("key", f". {nm}")])
        bar(LX, row, 6, full * v / wmax, c["levels"][3] if v == wmax else c["levels"][2])
        line(LX, row, [("val" if v == wmax else "text", val)], col=LCOLS - len(val))

    # ---------------- right column
    line(RX, 0, hdr("Weekly activity", RCOLS))
    cw_ = RCOLS * CW
    top, bottom = base(0) + 12, base(5) + 2
    peak = max(v for _, v in wk) or 1
    step = cw_ / len(wk)
    nz = sorted(v for _, v in wk if v > 0)
    cuts = [nz[int(len(nz) * q) - 1] for q in (0.25, 0.5, 0.75)] if len(nz) >= 4 else [1, 2, 3]
    for i, (d, v) in enumerate(wk):
        h = max(2, v / peak * (bottom - top))
        col = c["track"] if v <= 0 else c["levels"][sum(v > k for k in cuts)]
        o.append(f'<rect x="{RX + i * step + 0.6:.1f}" y="{bottom - h:.1f}" width="{step - 2:.1f}" '
                 f'height="{h:.1f}" rx="1" fill="{col}"/>')
    last, last_x = None, -99
    for i, (d, v) in enumerate(wk):
        x = RX + i * step
        if d.month != last and d.day <= 7:
            last = d.month
            if x - last_x >= 4 * CW and x + 3 * CW <= RX + cw_:
                o.append(f'<text class="info dots" x="{x:.1f}" y="{base(6):.1f}" textLength="{3 * CW}" '
                         f'lengthAdjust="spacing">{d.strftime("%b")}</text>')
                last_x = x

    line(RX, 8, hdr("Languages", RCOLS))
    langs = stats.get("languages") or []
    if langs:
        tot = sum(l[2] for l in langs) or 1
        x = RX
        for i, (name, col, size) in enumerate(langs):
            seg = cw_ * size / tot
            o.append(f'<rect x="{x:.1f}" y="{base(9) - 9.5:.1f}" width="{max(0, seg - 2):.1f}" height="9" rx="2" '
                     f'fill="{col or FALLBACK_COLORS[i % 6]}"/>')
            x += seg
        half = (RCOLS - 3) // 2
        for i in range(0, len(langs), 2):
            parts = []
            for j, (name, col, size) in enumerate(langs[i:i + 2]):
                if j:
                    parts.append(("dots", " | "))
                parts.append((col or FALLBACK_COLORS[(i + j) % 6], "■ "))
                parts += kv(name, f"{100 * size / tot:.0f}%", (half if j == 0 else RCOLS - half - 3) - 2, lead="")
            line(RX, 10 + i // 2, parts)
    else:
        line(RX, 10, [("dots", ". appears after the next stats run")])

    line(RX, 14, hdr("Activity", RCOLS))
    half = 26

    def pair(k1, v1, k2, v2):
        return kv(k1, v1, half) + [("dots", " | ")] + kv(k2, v2, RCOLS - half - 3, lead="")

    line(RX, 15, pair("Commits", fmt(stats.get("year_commits", "n/a")), "PRs", fmt(stats.get("prs", "n/a"))))
    line(RX, 16, pair("Issues", fmt(stats.get("issues", "n/a")),
                      "Repos touched", fmt(stats.get("contributed_repos", stats.get("contributed", "n/a")))))
    line(RX, 17, [("dots", ".")])
    sw = cw_ / len(PALETTE[0])
    for r, cols in enumerate(PALETTE):
        for i, col in enumerate(cols):
            o.append(f'<rect x="{RX + i * sw:.1f}" y="{base(18 + r) - 13:.1f}" width="{sw:.1f}" height="{LH:.1f}" fill="{col}"/>')

    o.append("</svg>")
    return "\n".join(o) + "\n"


def build(stats):
    if not stats.get("calendar"):
        print("no calendar data yet; skipping tracker")
        return
    for theme in ("dark", "light"):
        with open(os.path.join(HERE, f"tracker_{theme}.svg"), "w", encoding="utf-8") as f:
            f.write(render(theme, stats))
    print("wrote tracker_dark.svg and tracker_light.svg")
