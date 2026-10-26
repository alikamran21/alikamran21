"""Draws the work and stack card (stack_dark.svg / stack_light.svg).

Same card, colours and type as the header and the tracker. Edit WORK and STACK
below to change what it lists.
"""
import os
from xml.sax.saxutils import escape

from build_tracker import CW, FONT, LCOLS, LH, LX, PAD, RCOLS, RX, THEMES, W, hdr, kv

HERE = os.path.dirname(os.path.abspath(__file__))

WORK = [
    ("Foxy Audit", "CTO"),
    ("InvoiceMate", "DevOps Engineer"),
    ("coffeebean", "UEFN game dev"),
    ("GIKI", "Cyber Security, 3rd year"),
]
STACK = [
    ("Languages", "C, C++, Java, Python, Assembly"),
    ("Web", "HTML, CSS, JavaScript, TypeScript"),
    ("Data", "SQL, PL/pgSQL"),
    ("DevOps", "Git, GitHub Actions, Linux"),
    ("Tools", "VS Code, UEFN"),
]


def render(theme):
    c = THEMES[theme]
    rows = 1 + max(len(WORK), len(STACK))
    H = int(PAD * 2 + rows * LH - 6)
    o = ['<?xml version="1.0" encoding="UTF-8"?>',
         f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="{FONT}">',
         "<title>Work and stack</title>",
         "<style>",
         ".info{font-size:13.5px;white-space:pre}",
         f".text{{fill:{c['text']}}} .key{{fill:{c['key']}}} .val{{fill:{c['val']}}} .dots{{fill:{c['dots']}}}",
         "</style>",
         f'<rect width="{W}" height="{H}" rx="15" fill="{c["bg"]}" stroke="{c["border"]}"/>']

    def line(x, row, parts):
        n = sum(len(t) for _, t in parts)
        inner = "".join(f'<tspan class="{k}">{escape(t)}</tspan>' for k, t in parts)
        o.append(f'<text class="info" x="{x}" y="{PAD + 12 + row * LH:.1f}" textLength="{n * CW:.1f}" '
                 f'lengthAdjust="spacing" xml:space="preserve">{inner}</text>')

    line(LX, 0, hdr("Work", LCOLS))
    for i, (k, v) in enumerate(WORK, 1):
        line(LX, i, kv(k, v, LCOLS))
    line(RX, 0, hdr("Stack", RCOLS))
    for i, (k, v) in enumerate(STACK, 1):
        line(RX, i, kv(k, v, RCOLS))
    o.append("</svg>")
    return "\n".join(o) + "\n"


def build():
    for theme in ("dark", "light"):
        with open(os.path.join(HERE, f"stack_{theme}.svg"), "w", encoding="utf-8") as f:
            f.write(render(theme))
    print("wrote stack_dark.svg and stack_light.svg")


if __name__ == "__main__":
    build()
