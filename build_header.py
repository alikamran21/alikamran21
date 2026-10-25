"""Builds dark_mode.svg and light_mode.svg for the profile README header.

Usage:
    python build_header.py            # rebuild SVGs from stats.json
    python build_header.py --fetch    # refresh stats.json from GitHub first
                                      # (needs GITHUB_TOKEN and USER_NAME env vars)
"""
import datetime
import json
import os
import sys
import urllib.request
from xml.sax.saxutils import escape

HERE = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------- profile data
INFO = [
    ("hdr", "ali@kamran"),
    ("kv", "OS", "Windows 11, Android, Ubuntu CLI"),
    ("kv", "Education", "Cyber Security, 3rd Year @ GIKI"),
    ("kv", "Role.DevOps", "DevOps Engineer @ InvoiceMate"),
    ("kv", "Role.CTO", "CTO @ Foxy Audit"),
    ("kv", "IDE", "VS Code"),
    ("blank",),
    ("kv", "Lang.Programming", "Assembly, C, C++, Java, Python"),
    ("kv", "Lang.Computer", "HTML, CSS, JSON, and more"),
    ("kv", "Lang.Real", "English, Urdu"),
    ("blank",),
    ("kv", "Hobbies.Software", "Game Dev, UEFN (coffeebean)"),
    ("kv", "Hobbies.Other", "Gaming, Reading"),
    ("blank",),
    ("hdr", "Contact"),
    ("kv", "Email", "alikamran1223@gmail.com"),
    ("kv", "LinkedIn", "ali-kamran-182b3033b"),
    ("kv", "Discord", "coffee_.bean"),
    ("blank",),
    ("hdr", "GitHub Stats"),
    ("stats1",),
    ("stats2",),
]

THEMES = {
    "dark": dict(bg="#161b22", text="#c9d1d9", key="#ffa657", val="#a5d6ff",
                 dots="#616e7f", art="#c9d1d9", border="#30363d"),
    "light": dict(bg="#f6f8fa", text="#24292f", key="#953800", val="#0a3069",
                  dots="#a8b3c1", art="#24292f", border="#d0d7de"),
}

# ---------------------------------------------------------------- layout
W = 1000
PAD = 20
ART_X = PAD
ART_CW = 5.35         # px per art character
ART_LH = 10.4         # px per art line
INFO_X = 548
INFO_COLS = 54
INFO_CW = 8.0
INFO_LH = 19.5
ART_FS = 9
INFO_FS = 13.5

STATS_FILE = os.path.join(HERE, "stats.json")
DEFAULT_STATS = {"repos": 8, "contributed": "n/a", "stars": 0,
                 "commits": "n/a", "followers": 0}


def load_stats():
    try:
        with open(STATS_FILE) as f:
            return {**DEFAULT_STATS, **json.load(f)}
    except (OSError, ValueError):
        return dict(DEFAULT_STATS)


def gql(token, query, variables):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json",
                 "User-Agent": "profile-header-builder"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    if "errors" in data:
        raise RuntimeError(data["errors"])
    return data["data"]


def fetch_stats(user, token):
    base = gql(token, """
    query($login:String!){ user(login:$login){
      createdAt
      followers{totalCount}
      repositories(ownerAffiliations:OWNER, first:100){ totalCount nodes{stargazerCount} }
      repositoriesContributedTo(first:1, contributionTypes:[COMMIT,PULL_REQUEST,ISSUE,REPOSITORY]){ totalCount }
    }}""", {"login": user})["user"]
    start = int(base["createdAt"][:4])
    now = datetime.datetime.utcnow()
    parts = []
    for y in range(start, now.year + 1):
        parts.append(f'y{y}: contributionsCollection(from:"{y}-01-01T00:00:00Z", '
                     f'to:"{y}-12-31T23:59:59Z"){{ totalCommitContributions restrictedContributionsCount }}')
    commits = gql(token, "query($login:String!){ user(login:$login){ "
                  + " ".join(parts) + " }}", {"login": user})["user"]
    return {
        "repos": base["repositories"]["totalCount"],
        "contributed": base["repositoriesContributedTo"]["totalCount"],
        "stars": sum(n["stargazerCount"] for n in base["repositories"]["nodes"]),
        "commits": sum(v["totalCommitContributions"] + v["restrictedContributionsCount"] for v in commits.values()),
        "followers": base["followers"]["totalCount"],
    }


def fmt(n):
    return f"{n:,}" if isinstance(n, int) else str(n)


# ---------------------------------------------------------------- SVG pieces
def span(cls, text):
    return f'<tspan class="{cls}">{escape(text)}</tspan>'


def kv_line(key, val):
    head = f". {key}: "
    dots = max(2, INFO_COLS - len(head) - len(val) - 1)
    return [("key", f". {key}:"), ("dots", " " + "." * dots + " "), ("val", val)]


def two_col(a_key, a_val, b_key, b_val, split=30):
    """Two stat cells on one line: left cell is `split` wide, right fills the rest."""
    left_head = f". {a_key}: "
    ld = max(2, split - len(left_head) - len(a_val) - 1)
    left = [("key", f". {a_key}:"), ("dots", " " + "." * ld + " "), ("val", a_val)]
    right_head = f"{b_key}: "
    rd = max(2, INFO_COLS - split - 3 - len(right_head) - len(b_val) - 1)
    right = [("dots", " | "), ("key", f"{b_key}:"),
             ("dots", " " + "." * rd + " "), ("val", b_val)]
    return left + right


def build_lines(stats):
    rows = []
    for item in INFO:
        kind = item[0]
        if kind == "blank":
            rows.append([("dots", ".")])
        elif kind == "hdr":
            title = item[1] + " "
            pre = "- " if item[1] != "ali@kamran" else ""
            text = pre + title
            rows.append([("text", text), ("dots", "-" * (INFO_COLS - len(text)))])
        elif kind == "kv":
            rows.append(kv_line(item[1], item[2]))
        elif kind == "stats1":
            rows.append(two_col("Repos", f"{fmt(stats['repos'])} {{Contributed: {fmt(stats['contributed'])}}}",
                                "Stars", fmt(stats["stars"]), split=34))
        elif kind == "stats2":
            rows.append(two_col("Commits", fmt(stats["commits"]),
                                "Followers", fmt(stats["followers"]), split=34))
    return rows


def render(theme, stats):
    c = THEMES[theme]
    art = open(os.path.join(HERE, f"ascii_{theme}.txt")).read().rstrip("\n").split("\n")
    info = build_lines(stats)
    h = int(PAD * 2 + max(len(art) * ART_LH, len(info) * INFO_LH) + 6)

    out = [f'<?xml version="1.0" encoding="UTF-8"?>',
           f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{h}" viewBox="0 0 {W} {h}" '
           f'font-family="Consolas, \'Liberation Mono\', Menlo, \'DejaVu Sans Mono\', monospace">',
           "<title>Ali Kamran</title>",
           "<style>",
           f".art{{fill:{c['art']};font-size:{ART_FS}px;white-space:pre}}",
           f".info{{font-size:{INFO_FS}px;white-space:pre}}",
           f".text{{fill:{c['text']}}} .key{{fill:{c['key']}}} .val{{fill:{c['val']}}} .dots{{fill:{c['dots']}}}",
           "</style>",
           f'<rect width="{W}" height="{h}" rx="15" fill="{c["bg"]}" stroke="{c["border"]}"/>']

    for i, line in enumerate(art):
        if not line.strip():
            continue
        y = PAD + 10 + i * ART_LH
        out.append(f'<text class="art" x="{ART_X}" y="{y:.1f}" textLength="{len(line) * ART_CW:.1f}" '
                   f'lengthAdjust="spacing" xml:space="preserve">{escape(line)}</text>')

    for i, parts in enumerate(info):
        y = PAD + 12 + i * INFO_LH
        total = sum(len(t) for _, t in parts)
        inner = "".join(span(cls, t) for cls, t in parts)
        out.append(f'<text class="info" x="{INFO_X}" y="{y:.1f}" textLength="{total * INFO_CW:.1f}" '
                   f'lengthAdjust="spacing" xml:space="preserve">{inner}</text>')

    out.append("</svg>")
    return "\n".join(out) + "\n"


def main():
    stats = load_stats()
    if "--fetch" in sys.argv:
        user, token = os.environ.get("USER_NAME"), os.environ.get("GITHUB_TOKEN")
        try:
            stats = fetch_stats(user, token)
            with open(STATS_FILE, "w") as f:
                json.dump(stats, f, indent=2)
            print("stats refreshed:", stats)
        except Exception as e:  # keep the last known numbers if the API call fails
            print("could not refresh stats, using cached values:", e)
    for theme in ("dark", "light"):
        with open(os.path.join(HERE, f"{theme}_mode.svg"), "w") as f:
            f.write(render(theme, stats))
    print("wrote dark_mode.svg and light_mode.svg")


if __name__ == "__main__":
    main()
