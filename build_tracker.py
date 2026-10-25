"""Draws the contribution tracker (tracker_dark.svg / tracker_light.svg).

Data comes from the same stats.json that build_header.py maintains. The
"calendar" key holds [[YYYY-MM-DD, count], ...] for the last year.
"""
import datetime
import os
from xml.sax.saxutils import escape

HERE = os.path.dirname(os.path.abspath(__file__))

THEMES = {
    "dark": dict(bg="#0d1117", border="#30363d", text="#e6edf3", muted="#8b949e",
                 bar="#2ea043", bar_dim="#1f6f33", track="#21262d"),
    "light": dict(bg="#ffffff", border="#d0d7de", text="#1f2328", muted="#57606a",
                  bar="#1a7f37", bar_dim="#8ad3a0", track="#eaeef2"),
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


def render(theme, stats):
    c = THEMES[theme]
    a = analyse(stats["calendar"])
    year_total = stats.get("year_total", a["total"])
    W, H = 1000, 452
    pad = 28
    o = [f'<?xml version="1.0" encoding="UTF-8"?>',
         f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="{FONT}">',
         "<title>Contribution tracker</title>",
         f'<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="6" fill="{c["bg"]}" stroke="{c["border"]}"/>']

    def hline(y):
        o.append(f'<line x1="0" y1="{y}" x2="{W}" y2="{y}" stroke="{c["border"]}"/>')

    def vline(x, y1, y2):
        o.append(f'<line x1="{x}" y1="{y1}" x2="{x}" y2="{y2}" stroke="{c["border"]}"/>')

    # row 1: totals and streaks
    all_time = stats.get("all_time_total", year_total)
    joined = stats.get("joined")
    since = (f"{_date(joined).strftime('%b')} {_date(joined).day}, {_date(joined).year} - present") if joined \
        else f"{fmt(a['active_days'])} active days in the last year"
    cols = [("Total contributions", fmt(all_time), since),
            ("Current streak", f"{a['current']} days", rng(a["current_range"])),
            ("Longest streak", f"{a['longest']} days", rng(a["longest_range"]))]
    cw = W / 3
    for i, (label, big, sub) in enumerate(cols):
        x = i * cw + pad
        o.append(f'<text x="{x:.1f}" y="40" font-size="12" fill="{c["muted"]}">{escape(label)}</text>')
        o.append(f'<text x="{x:.1f}" y="76" font-size="28" font-weight="600" fill="{c["text"]}">{escape(big)}</text>')
        o.append(f'<text x="{x:.1f}" y="98" font-size="12" fill="{c["muted"]}">{escape(sub)}</text>')
        if i:
            vline(i * cw, 20, 106)
    hline(124)

    # row 2: activity numbers and languages
    mid = W / 2
    vline(mid, 124, 268)
    o.append(f'<text x="{pad}" y="154" font-size="13" font-weight="600" fill="{c["text"]}">Activity</text>')
    rows = [("Stars earned", fmt(stats.get("stars", 0))),
            ("Commits, last year", fmt(stats.get("year_commits", "n/a"))),
            ("Pull requests", fmt(stats.get("prs", "n/a"))),
            ("Issues", fmt(stats.get("issues", "n/a"))),
            ("Repositories contributed to", fmt(stats.get("contributed_repos", stats.get("contributed", "n/a"))))]
    for i, (k, v) in enumerate(rows):
        y = 180 + i * 18
        o.append(f'<text x="{pad}" y="{y}" font-size="12" fill="{c["muted"]}">{escape(k)}</text>')
        o.append(f'<text x="{mid - pad}" y="{y}" font-size="12" font-weight="600" text-anchor="end" fill="{c["text"]}">{escape(v)}</text>')

    lx = mid + pad
    lw = W - pad - lx
    o.append(f'<text x="{lx}" y="154" font-size="13" font-weight="600" fill="{c["text"]}">Languages</text>')
    langs = stats.get("languages") or []
    if langs:
        tot = sum(l[2] for l in langs) or 1
        o.append(f'<clipPath id="lc-{theme}"><rect x="{lx}" y="166" width="{lw}" height="8" rx="4"/></clipPath>')
        x = lx
        for i, (name, col, size) in enumerate(langs):
            seg = lw * size / tot
            o.append(f'<rect x="{x:.1f}" y="166" width="{seg + 0.6:.1f}" height="8" fill="{col or FALLBACK_COLORS[i % 6]}" clip-path="url(#lc-{theme})"/>')
            x += seg
        for i, (name, col, size) in enumerate(langs):
            colx = lx + (i % 3) * (lw / 3)
            y = 200 + (i // 3) * 22
            o.append(f'<circle cx="{colx + 4:.1f}" cy="{y - 4}" r="4" fill="{col or FALLBACK_COLORS[i % 6]}"/>')
            o.append(f'<text x="{colx + 14:.1f}" y="{y}" font-size="12" fill="{c["text"]}">{escape(name)} '
                     f'<tspan fill="{c["muted"]}">{100 * size / tot:.1f}%</tspan></text>')
    hline(268)

    # row 3: contributions per month
    o.append(f'<text x="{pad}" y="298" font-size="13" font-weight="600" fill="{c["text"]}">Contributions per month</text>')
    months = a["months"]
    peak = max(v for _, v in months) or 1
    left, width, base, maxh = pad, W - 2 * pad, 420, 96
    slot = width / len(months)
    bw = slot * 0.5
    for i, ((yr, mo), v) in enumerate(months):
        h = max(2, v / peak * maxh)
        x = left + i * slot + (slot - bw) / 2
        fill = c["bar"] if v == peak else c["bar_dim"]
        o.append(f'<rect x="{x:.1f}" y="{base - 18 - h:.1f}" width="{bw:.1f}" height="{h:.1f}" rx="2" fill="{fill}"/>')
        o.append(f'<text x="{x + bw / 2:.1f}" y="{base - 24 - h:.1f}" font-size="11" text-anchor="middle" fill="{c["muted"]}">{fmt(v)}</text>')
        o.append(f'<text x="{x + bw / 2:.1f}" y="{base - 2}" font-size="11" text-anchor="middle" fill="{c["muted"]}">{datetime.date(yr, mo, 1).strftime("%b")}</text>')

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
