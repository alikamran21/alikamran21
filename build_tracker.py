"""Draws the contribution tracker (tracker_dark.svg / tracker_light.svg).

Data comes from the same stats.json that build_header.py maintains; the
"calendar" key holds [[YYYY-MM-DD, count], ...] for the last year.
"""
import datetime
import os
from xml.sax.saxutils import escape

HERE = os.path.dirname(os.path.abspath(__file__))

THEMES = {
    "dark": dict(bg="#161b22", tile="#0d1117", border="#30363d", text="#c9d1d9",
                 muted="#8b949e", accent="#39d353", accent2="#0e4429", hot="#ffa657"),
    "light": dict(bg="#f6f8fa", tile="#ffffff", border="#d0d7de", text="#24292f",
                  muted="#57606a", accent="#216e39", accent2="#aceebb", hot="#953800"),
}

CALENDAR_QUERY = """
query($login:String!){ user(login:$login){ contributionsCollection{
  totalPullRequestContributions totalIssueContributions totalPullRequestReviewContributions
  contributionCalendar{ totalContributions weeks{ contributionDays{ date contributionCount } } }
}}}"""


def fetch_calendar(gql, token, user):
    cc = gql(token, CALENDAR_QUERY, {"login": user})["user"]["contributionsCollection"]
    days = [[d["date"], d["contributionCount"]]
            for w in cc["contributionCalendar"]["weeks"] for d in w["contributionDays"]]
    return {
        "calendar": days,
        "year_total": cc["contributionCalendar"]["totalContributions"],
        "prs": cc["totalPullRequestContributions"],
        "issues": cc["totalIssueContributions"],
        "reviews": cc["totalPullRequestReviewContributions"],
    }


def _date(s):
    return datetime.date.fromisoformat(s)


def analyse(calendar):
    days = sorted((_date(d), c) for d, c in calendar)
    today = datetime.date.today()
    days = [(d, c) for d, c in days if d <= today] or days

    longest = run = 0
    for _, c in days:
        run = run + 1 if c > 0 else 0
        longest = max(longest, run)

    cur = 0
    for i in range(len(days) - 1, -1, -1):
        if days[i][1] > 0:
            cur += 1
        elif i == len(days) - 1:  # today still empty: streak is not broken yet
            continue
        else:
            break

    best = max(days, key=lambda x: x[1])
    months = {}
    for d, c in days:
        months[(d.year, d.month)] = months.get((d.year, d.month), 0) + c
    keys = sorted(months)[-12:]
    return dict(total=sum(c for _, c in days), current=cur, longest=longest,
                best_day=best, months=[(k, months[k]) for k in keys],
                active_days=sum(1 for _, c in days if c > 0))


def fmt(n):
    return f"{n:,}"


def render(theme, stats):
    c = THEMES[theme]
    a = analyse(stats["calendar"])
    total = stats.get("year_total", a["total"])
    W, H = 1000, 330
    font = "Consolas, 'Liberation Mono', Menlo, 'DejaVu Sans Mono', monospace"
    o = [f'<?xml version="1.0" encoding="UTF-8"?>',
         f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="{font}">',
         "<title>Contribution tracker</title>",
         f'<rect width="{W}" height="{H}" rx="15" fill="{c["bg"]}" stroke="{c["border"]}"/>',
         f'<text x="24" y="34" font-size="15" font-weight="bold" fill="{c["text"]}">Contribution tracker</text>',
         f'<text x="{W - 24}" y="34" font-size="12" text-anchor="end" fill="{c["muted"]}">last 12 months</text>']

    tiles = [
        ("Total contributions", fmt(total), f"{fmt(a['active_days'])} active days"),
        ("Current streak", f"{a['current']}", "days in a row"),
        ("Longest streak", f"{a['longest']}", "days in a row"),
        ("Best day", fmt(a["best_day"][1]), a["best_day"][0].strftime("%b %d, %Y")),
    ]
    tw, gap, x0, y0, th = 229, 12, 24, 52, 84
    for i, (label, big, sub) in enumerate(tiles):
        x = x0 + i * (tw + gap)
        o.append(f'<rect x="{x}" y="{y0}" width="{tw}" height="{th}" rx="10" fill="{c["tile"]}" stroke="{c["border"]}"/>')
        o.append(f'<text x="{x + 16}" y="{y0 + 24}" font-size="12" fill="{c["muted"]}">{escape(label)}</text>')
        o.append(f'<text x="{x + 16}" y="{y0 + 56}" font-size="28" font-weight="bold" fill="{c["accent"]}">{escape(big)}</text>')
        o.append(f'<text x="{x + 16}" y="{y0 + 75}" font-size="11" fill="{c["muted"]}">{escape(sub)}</text>')

    # monthly bars
    cx, cy, cw, ch = 24, 160, W - 48, 130
    o.append(f'<text x="{cx}" y="{cy}" font-size="12" fill="{c["muted"]}">Contributions per month</text>')
    months = a["months"]
    peak = max(v for _, v in months) or 1
    slot = cw / len(months)
    bw = slot * 0.56
    base = cy + ch
    for i, ((yr, mo), v) in enumerate(months):
        bh = max(3, (v / peak) * (ch - 40)) if v else 3
        x = cx + i * slot + (slot - bw) / 2
        fill = c["accent"] if v == peak else c["accent2"] if v == 0 else c["accent"]
        op = 1 if v == peak else (0.35 if v == 0 else 0.55 + 0.45 * v / peak)
        label = datetime.date(yr, mo, 1).strftime("%b")
        o.append(f'<rect x="{x:.1f}" y="{base - bh - 22:.1f}" width="{bw:.1f}" height="{bh:.1f}" rx="4" fill="{fill}" opacity="{op:.2f}"/>')
        o.append(f'<text x="{x + bw / 2:.1f}" y="{base - bh - 28:.1f}" font-size="11" text-anchor="middle" fill="{c["text"]}">{fmt(v)}</text>')
        o.append(f'<text x="{x + bw / 2:.1f}" y="{base - 6}" font-size="11" text-anchor="middle" fill="{c["muted"]}">{label}</text>')

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
