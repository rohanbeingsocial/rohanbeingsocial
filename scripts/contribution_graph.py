"""Render the last year of contributions as a self-contained animated SVG.

Reads the calendar from GitHub's GraphQL API and writes a light and a dark
variant into assets/. The cells fade in column by column on load, so the grid
draws itself left to right; the sweep is disabled under prefers-reduced-motion.

Usage: GITHUB_TOKEN=... python scripts/contribution_graph.py [login]
"""
import json
import os
import sys
import urllib.request
from datetime import datetime

LOGIN = sys.argv[1] if len(sys.argv) > 1 else "rohanbeingsocial"
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")

QUERY = """
query($login:String!){
  user(login:$login){
    contributionsCollection{
      contributionCalendar{
        totalContributions
        weeks{ contributionDays{ date contributionCount contributionLevel weekday } }
      }
    }
  }
}
"""

THEMES = {
    "light": {
        "levels": ["#ebedf0", "#9be9a8", "#40c463", "#30a14e", "#216e39"],
        "text": "#59636e", "caption": "#1f2328",
    },
    "dark": {
        "levels": ["#151b23", "#033a16", "#196c2e", "#2ea043", "#56d364"],
        "text": "#9198a1", "caption": "#f0f6fc",
    },
}
LEVEL = {
    "NONE": 0, "FIRST_QUARTILE": 1, "SECOND_QUARTILE": 2,
    "THIRD_QUARTILE": 3, "FOURTH_QUARTILE": 4,
}

CELL, GAP = 11, 3
PITCH = CELL + GAP
PAD_L, PAD_T = 30, 40
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def fetch(login, token):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": login}}).encode(),
        headers={"Authorization": f"bearer {token}",
                 "Content-Type": "application/json",
                 "User-Agent": "contribution-graph"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        payload = json.load(r)
    if "errors" in payload:
        raise SystemExit(f"GraphQL error: {payload['errors']}")
    return payload["data"]["user"]["contributionsCollection"]["contributionCalendar"]


def render(cal, theme_name):
    t = THEMES[theme_name]
    weeks = cal["weeks"]
    width = PAD_L + len(weeks) * PITCH - GAP + 6
    height = PAD_T + 7 * PITCH - GAP + 6

    # The sweep lives inside the keyframes, one set per column, rather than in
    # animation-delay with a backwards fill, and it animates scale only -- never
    # opacity. Both choices exist so the grid degrades to something correct:
    # a renderer that drops the CSS falls back to each cell's resting state,
    # and one that parses the CSS but freezes the timeline at 0% still paints
    # every cell in full colour, just smaller. Motion is additive here; it is
    # never what makes a cell visible.
    n = max(len(weeks) - 1, 1)
    frames = []
    for i in range(len(weeks)):
        start = round(i / n * 45, 2)
        end = round(start + 25, 2)
        frames.append(
            f"@keyframes k{i}{{0%,{start}%{{transform:scale(.7)}}"
            f"{end}%,100%{{transform:scale(1)}}}}"
            f".c{i}{{animation:k{i} 1.4s cubic-bezier(.2,.85,.3,1)}}"
        )
    css = (
        f"<style>"
        f".d{{transform-box:fill-box;transform-origin:50% 50%}}"
        f"{''.join(frames)}"
        f"@media(prefers-reduced-motion:reduce){{.d{{animation:none}}}}"
        f"text{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif}}"
        f"</style>"
    )

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="{cal["totalContributions"]} contributions in the last year">',
        css,
        f'<text x="0" y="13" fill="{t["caption"]}" font-size="12" font-weight="600">'
        f'{cal["totalContributions"]:,} contributions in the last year</text>',
    ]

    # month labels, printed once per month at the week it first appears
    seen = set()
    for wi, week in enumerate(weeks):
        d = datetime.strptime(week["contributionDays"][0]["date"], "%Y-%m-%d")
        if d.month not in seen and d.day <= 14:
            seen.add(d.month)
            x = PAD_L + wi * PITCH
            parts.append(f'<text x="{x}" y="{PAD_T - 8}" fill="{t["text"]}" '
                         f'font-size="10">{MONTHS[d.month - 1]}</text>')

    for label, wd in (("Mon", 1), ("Wed", 3), ("Fri", 5)):
        y = PAD_T + wd * PITCH + CELL - 2
        parts.append(f'<text x="0" y="{y}" fill="{t["text"]}" font-size="9">{label}</text>')

    for wi, week in enumerate(weeks):
        for day in week["contributionDays"]:
            lvl = LEVEL[day["contributionLevel"]]
            x = PAD_L + wi * PITCH
            y = PAD_T + day["weekday"] * PITCH
            n = day["contributionCount"]
            plural = "" if n == 1 else "s"
            parts.append(
                f'<rect class="d c{wi}" x="{x}" y="{y}" width="{CELL}" height="{CELL}" '
                f'rx="2" fill="{t["levels"][lvl]}">'
                f'<title>{n} contribution{plural} on {day["date"]}</title></rect>'
            )

    parts.append("</svg>")
    return "".join(parts)


def main():
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        raise SystemExit("set GITHUB_TOKEN")
    cal = fetch(LOGIN, token)
    os.makedirs(OUT, exist_ok=True)
    for name in THEMES:
        path = os.path.join(OUT, f"contributions-{name}.svg")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(render(cal, name))
        print(f"wrote {path} ({os.path.getsize(path)} bytes)")
    print(f"{cal['totalContributions']} contributions")


if __name__ == "__main__":
    main()
