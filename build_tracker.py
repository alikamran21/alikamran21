"""Draws the contribution tracker (tracker_dark.svg / tracker_light.svg).

Data comes from the same stats.json that build_header.py maintains. The
"calendar" key holds [[YYYY-MM-DD, count], ...] for the last year.
"""
import datetime
import os
from xml.sax.saxutils import escape

HERE = os.path.dirname(os.path.abspath(__file__))

THEMES = {
    "dark": dict(bg="#0d1117", card="#161b22", border="#30363d", text="#e6edf3", muted="#8b949e",
                 hi="#39d353", mid="#2ea043", lo="#1f6f33", flame="#ffa657", flame2="#ffd8a8"),
    "light": dict(bg="#ffffff", card="#f6f8fa", border="#d0d7de", text="#1f2328", muted="#57606a",
                  hi="#1a7f37", mid="#4ac26b", lo="#aceebb", flame="#bc4c00", flame2="#ffb77c"),
}
FONT = "-apple-system, 'Segoe UI', Helvetica, Arial, sans-serif"
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


FLAME = "M0 -15 C 7 -7, 11 -2, 11 6 A11 11 0 0 1 -11 6 C -11 0, -5 -4, 0 -15 Z"
FLAME_IN = "M0 -4 C 4 0, 6 3, 6 7 A6 6 0 0 1 -6 7 C -6 4, -3 1, 0 -4 Z"
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


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

    W, H = 1000, 524
    o = [f'<?xml version="1.0" encoding="UTF-8"?>',
         f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="{FONT}">',
         "<title>Contribution tracker</title>",
         f'<rect width="{W}" height="{H}" fill="{c["bg"]}"/>']

    def card(x, y, w, h):
        o.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="14" fill="{c["card"]}" stroke="{c["border"]}"/>')

    def t(x, y, s, size=12, fill=None, weight=400, anchor="start", extra=""):
        o.append(f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{weight}" fill="{fill or c["text"]}" '
                 f'text-anchor="{anchor}" {extra}>{escape(str(s))}</text>')

    # ---- row 1: total, current streak, longest streak
    all_time = stats.get("all_time_total", stats.get("year_total", a["total"]))
    joined = stats.get("joined")
    since = (f"since {_date(joined).strftime('%b')} {_date(joined).day}, {_date(joined).year}") if joined \
        else f"{fmt(a['active_days'])} active days in the last year"
    tw = (W - 24 - 24) / 3
    xs = [12 + i * (tw + 12) for i in range(3)]
    for x in xs:
        card(x, 12, tw, 140)
    t(xs[0] + 22, 46, "Total contributions", 13, c["muted"])
    t(xs[0] + 22, 104, fmt(all_time), 48, weight=700)
    t(xs[0] + 22, 132, since, 12, c["muted"])

    o.append(f'<g transform="translate({xs[1] + 32},{40})"><path d="{FLAME}" fill="{c["flame"]}"/><path d="{FLAME_IN}" fill="{c["flame2"]}"/></g>')
    t(xs[1] + 54, 46, "Current streak", 13, c["muted"])
    t(xs[1] + 22, 94, f"{a['current']} days", 34, weight=700)
    t(xs[1] + 22, 116, rng(a["current_range"]), 12, c["muted"])
    bar_w = tw - 44
    o.append(f'<rect x="{xs[1] + 22}" y="128" width="{bar_w}" height="6" rx="3" fill="{c["border"]}"/>')
    frac = min(1, a["current"] / a["longest"]) if a["longest"] else 0
    o.append(f'<rect x="{xs[1] + 22}" y="128" width="{bar_w * frac:.1f}" height="6" rx="3" fill="{c["flame"]}"/>')

    t(xs[2] + 22, 46, "Longest streak", 13, c["muted"])
    t(xs[2] + 22, 94, f"{a['longest']} days", 34, weight=700)
    t(xs[2] + 22, 116, rng(a["longest_range"]), 12, c["muted"])
    o.append(f'<rect x="{xs[2] + 22}" y="128" width="{bar_w}" height="6" rx="3" fill="{c["hi"]}"/>')

    # ---- row 2: weekly activity and weekday split
    y2, h2 = 164, 204
    wx, ww = 12, 612
    card(wx, y2, ww, h2)
    t(wx + 22, y2 + 32, "Weekly activity", 13, c["muted"])
    t(wx + ww - 22, y2 + 32, "last 12 months", 11, c["muted"], anchor="end")
    bx, by, bw_, bh = wx + 22, y2 + 52, ww - 44, 110
    peak = max(v for _, v in wk) or 1
    step = bw_ / len(wk)
    for i, (d, v) in enumerate(wk):
        h = max(2, v / peak * bh)
        col = c["hi"] if v > peak * .7 else c["mid"] if v > peak * .2 else c["lo"]
        o.append(f'<rect x="{bx + i * step + 1:.1f}" y="{by + bh - h:.1f}" width="{step - 2.4:.1f}" height="{h:.1f}" rx="1.5" fill="{col}"/>')
    last = None
    for i, (d, v) in enumerate(wk):
        if d.month != last and d.day <= 7:
            t(f"{bx + i * step:.1f}", by + bh + 20, d.strftime("%b"), 10, c["muted"])
            last = d.month

    wx2 = wx + ww + 12
    ww2 = W - 12 - wx2
    card(wx2, y2, ww2, h2)
    t(wx2 + 22, y2 + 32, "By weekday", 13, c["muted"])
    wmax = max(wd) or 1
    for i, (nm, v) in enumerate(zip(WEEKDAYS, wd)):
        y = y2 + 52 + i * 21
        t(wx2 + 22, y + 11, nm, 12, c["muted"])
        ln = (ww2 - 130) * v / wmax
        o.append(f'<rect x="{wx2 + 62}" y="{y}" width="{ln:.1f}" height="13" rx="3" fill="{c["hi"] if v == wmax else c["lo"]}"/>')
        t(f"{wx2 + 68 + ln:.1f}", y + 11, fmt(v), 11, c["text"] if v == wmax else c["muted"])

    # ---- row 3: languages and stat chips
    y3, h3 = y2 + h2 + 12, 136
    card(12, y3, W - 24, h3)
    t(34, y3 + 32, "Languages", 13, c["muted"])
    langs = stats.get("languages") or []
    if langs:
        tot = sum(l[2] for l in langs) or 1
        lw = W - 68
        o.append(f'<clipPath id="lc-{theme}"><rect x="34" y="{y3 + 44}" width="{lw}" height="12" rx="6"/></clipPath>')
        x = 34
        for i, (name, col, size) in enumerate(langs):
            seg = lw * size / tot
            o.append(f'<rect x="{x:.1f}" y="{y3 + 44}" width="{seg + 0.6:.1f}" height="12" fill="{col or FALLBACK_COLORS[i % 6]}" clip-path="url(#lc-{theme})"/>')
            x += seg
        for i, (name, col, size) in enumerate(langs):
            lx = 34 + i * (lw / 6)
            o.append(f'<circle cx="{lx + 4:.1f}" cy="{y3 + 78}" r="4" fill="{col or FALLBACK_COLORS[i % 6]}"/>')
            t(f"{lx + 15:.1f}", y3 + 82, f"{name} {100 * size / tot:.0f}%", 12)
    else:
        t(34, y3 + 66, "Appears after the next stats run", 12, c["muted"])
    chips = [("Commits", fmt(stats.get("year_commits", "n/a"))), ("PRs", fmt(stats.get("prs", "n/a"))),
             ("Repos", fmt(stats.get("contributed_repos", stats.get("contributed", "n/a")))),
             ("Stars", fmt(stats.get("stars", 0))), ("Active days", f"{a['active_days']}")]
    x = 34
    for k, v in chips:
        w_ = 26 + (len(k) + len(v) + 2) * 6.6
        o.append(f'<rect x="{x:.1f}" y="{y3 + 98}" width="{w_:.1f}" height="26" rx="13" fill="{c["bg"]}" stroke="{c["border"]}"/>')
        t(f"{x + 13:.1f}", y3 + 115, k, 11, c["muted"])
        t(f"{x + 13 + (len(k) + 1) * 6.4:.1f}", y3 + 115, v, 11, weight=700)
        x += w_ + 8

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
