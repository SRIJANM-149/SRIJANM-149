#!/usr/bin/env python3
"""Generates stats.svg, langs.svg and activity.svg from the GitHub API, and
leetcode.svg from LeetCode's public profile data.

Needs GH_TOKEN with read access to the owner's private repos. Only totals are
written out: no private repo names, messages or code reach the cards.
"""
import json, os, sys, urllib.error, urllib.request
from collections import Counter
from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path

USER = "SRIJANM-149"
LEETCODE_USER = "Srijan_Q"
OUT = Path(__file__).resolve().parent.parent
IST = timezone(timedelta(hours=5, minutes=30))
TOKEN = os.environ["GH_TOKEN"]
GOLD, GREY = "#f5b041", "#9a9aa6"
FONT = "font-family=\"'Segoe UI',Ubuntu,Sans-Serif\""
BAR = ["#f5b041", "#e59866", "#c39bd3", "#7fb3d5", "#76d7c4", "#9a9aa6", "#ec7063"]
IGNORED_LANGS = {"Batchfile"}  # helper scripts, not a language I work in
DIFFICULTY = [("Easy", "#00b8a3"), ("Medium", "#ffc01e"), ("Hard", "#ef4743")]


def get(path):
    req = urllib.request.Request(
        "https://api.github.com" + path,
        headers={"Authorization": f"Bearer {TOKEN}", "Accept": "application/vnd.github+json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        if e.code == 409:  # empty repository
            return []
        raise


def paged(path):
    sep = "&" if "?" in path else "?"
    page, out = 1, []
    while True:
        items = get(f"{path}{sep}per_page=100&page={page}")
        out += items
        if len(items) < 100:
            return out
        page += 1


def collect():
    repos = [r for r in paged("/user/repos?affiliation=owner") if not r["fork"]]
    if not any(r["private"] for r in repos):
        sys.exit("Token sees no private repos; refusing to overwrite the cards with public-only totals.")
    shas, days, langs = set(), set(), Counter()
    for r in repos:
        name = r["full_name"]
        langs.update({k: v for k, v in get(f"/repos/{name}/languages").items() if k not in IGNORED_LANGS})
        for c in paged(f"/repos/{name}/commits?author={USER}"):
            if c["sha"] not in shas:
                shas.add(c["sha"])
                when = datetime.fromisoformat(c["commit"]["author"]["date"].replace("Z", "+00:00"))
                days.add(when.astimezone(IST).date())
    count = lambda q: get(f"/search/issues?q=author:{USER}+type:{q}&per_page=1")["total_count"]
    return {
        "commits": len(shas),
        "repos": len(repos),
        "stars": sum(r["stargazers_count"] for r in repos),
        "prs": count("pr"),
        "issues": count("issue"),
        "days": days,
        "langs": langs,
    }


def leetcode():
    query = """query($u: String!) {
      allQuestionsCount { difficulty count }
      matchedUser(username: $u) {
        submitStatsGlobal { acSubmissionNum { difficulty count submissions } }
        languageProblemCount { languageName problemsSolved }
      }
    }"""
    req = urllib.request.Request(
        "https://leetcode.com/graphql",
        data=json.dumps({"query": query, "variables": {"u": LEETCODE_USER}}).encode(),
        headers={"Content-Type": "application/json", "Referer": "https://leetcode.com", "User-Agent": "Mozilla/5.0"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.load(r)["data"]
    user = data["matchedUser"]
    return {
        "total": {q["difficulty"]: q["count"] for q in data["allQuestionsCount"]},
        "solved": {q["difficulty"]: q["count"] for q in user["submitStatsGlobal"]["acSubmissionNum"]},
        "accepted": next(q["submissions"] for q in user["submitStatsGlobal"]["acSubmissionNum"] if q["difficulty"] == "All"),
        "langs": sorted(((l["languageName"], l["problemsSolved"]) for l in user["languageProblemCount"]), key=lambda x: -x[1]),
    }


def longest_streak(days):
    best = run = 0
    prev = None
    for d in sorted(days):
        run = run + 1 if prev and d - prev == timedelta(days=1) else 1
        best = max(best, run)
        prev = d
    return best


def card(w, h, title, body, label):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" '
        f'aria-label="{escape(label)}" {FONT}><title>{escape(label)}</title>'
        f'<text x="25" y="35" fill="{GOLD}" font-size="18" font-weight="600">{escape(title)}</text>{body}</svg>\n'
    )


def stats_svg(s, asof):
    rows = [("Total commits", s["commits"]), ("Repositories", s["repos"]), ("Stars earned", s["stars"]),
            ("Pull requests", s["prs"]), ("Issues", s["issues"])]
    body = "".join(
        f'<text x="25" y="{62 + i * 22}" fill="{GREY}" font-size="14">{a}:</text>'
        f'<text x="300" y="{62 + i * 22}" fill="{GREY}" font-size="14" font-weight="700" text-anchor="end">{b:,}</text>'
        for i, (a, b) in enumerate(rows)
    )
    body += f'<text x="25" y="178" fill="{GREY}" font-size="10" opacity=".8">Includes private repos · as of {asof}</text>'
    label = "GitHub stats: " + ", ".join(f"{a} {b}" for a, b in rows)
    return card(325, 190, "GitHub stats", body, label)


def langs_svg(langs):
    total = sum(langs.values())
    top = langs.most_common(7)
    x, bar = 25, ""
    for i, (_, n) in enumerate(top):
        w = 250 * n / total
        bar += f'<rect x="{x:.2f}" y="50" width="{w:.2f}" height="8" fill="{BAR[i]}"/>'
        x += w
    rows = ""
    for i, (name, n) in enumerate(top):
        cx, y = 25 + (i % 2) * 135, 85 + (i // 2) * 28
        rows += (f'<circle cx="{cx + 5}" cy="{y - 4}" r="5" fill="{BAR[i]}"/>'
                 f'<text x="{cx + 16}" y="{y}" fill="{GREY}" font-size="11">{escape(name)} {100 * n / total:.1f}%</text>')
    label = "Most used languages: " + ", ".join(f"{a} {100 * b / total:.1f}%" for a, b in top)
    return card(300, 190, "Most used languages", bar + rows, label)


def activity_svg(s, last):
    cols = [(f'{len(s["days"]):,}', "Active days"), (str(longest_streak(s["days"])), "Longest streak (days)"), (last, "Last commit")]
    body = "".join(
        f'<text x="{105 + i * 195}" y="72" fill="{GOLD}" font-size="{26 if i < 2 else 20}" font-weight="700" text-anchor="middle">{a}</text>'
        f'<text x="{105 + i * 195}" y="98" fill="{GREY}" font-size="12" text-anchor="middle">{b}</text>'
        for i, (a, b) in enumerate(cols)
    )
    label = "Activity: " + ", ".join(f"{b} {a}" for a, b in cols)
    return card(600, 115, "Activity", body, label)


def leetcode_svg(lc, asof):
    solved = lc["solved"]
    body = (f'<text x="95" y="84" fill="{GOLD}" font-size="34" font-weight="700" text-anchor="middle">{solved["All"]:,}</text>'
            f'<text x="95" y="106" fill="{GREY}" font-size="12" text-anchor="middle">problems solved</text>')
    x, bar = 200.0, ""
    for name, colour in DIFFICULTY:
        w = 375 * solved[name] / max(solved["All"], 1)
        if w:
            bar += f'<rect x="{x:.2f}" y="58" width="{w:.2f}" height="8" fill="{colour}"/>'
        x += w
    if not bar:
        bar = f'<rect x="200" y="58" width="375" height="8" fill="{GREY}" opacity=".25"/>'
    for i, (name, colour) in enumerate(DIFFICULTY):
        cx = 200 + i * 125
        bar += (f'<circle cx="{cx + 5}" cy="86" r="5" fill="{colour}"/>'
                f'<text x="{cx + 16}" y="90" fill="{GREY}" font-size="12">{name} '
                f'<tspan font-weight="700">{solved[name]}</tspan> / {lc["total"][name]:,}</text>')
    langs = ", ".join(f"{n} {c}" for n, c in lc["langs"]) or "none yet"
    bar += (f'<text x="200" y="118" fill="{GREY}" font-size="11">{lc["accepted"]:,} accepted submissions · '
            f'{escape(langs)} · as of {asof}</text>')
    label = (f"LeetCode: {solved['All']} problems solved, " +
             ", ".join(f"{n} {solved[n]} of {lc['total'][n]}" for n, _ in DIFFICULTY) + f", languages {langs}")
    return card(600, 140, f"LeetCode · {LEETCODE_USER}", body + bar, label)


def main():
    s = collect()
    d = max(s["days"])
    last = f"{d:%b} {d.day}, {d.year}"
    (OUT / "stats.svg").write_text(stats_svg(s, last), encoding="utf-8", newline="\n")
    (OUT / "langs.svg").write_text(langs_svg(s["langs"]), encoding="utf-8", newline="\n")
    (OUT / "activity.svg").write_text(activity_svg(s, last), encoding="utf-8", newline="\n")
    try:
        lc = leetcode()
    except Exception as e:  # LeetCode being down shouldn't block the GitHub cards
        print("LeetCode fetch failed, keeping the old card:", e)
    else:
        today = datetime.now(IST).date()
        (OUT / "leetcode.svg").write_text(leetcode_svg(lc, f"{today:%b} {today.day}, {today.year}"), encoding="utf-8", newline="\n")
        print("leetcode", lc["solved"], lc["langs"])
    total = sum(s["langs"].values())
    print({k: s[k] for k in ("commits", "repos", "stars", "prs", "issues")}, "active_days", len(s["days"]),
          "longest", longest_streak(s["days"]), "last", last,
          [(a, round(100 * b / total, 1)) for a, b in s["langs"].most_common(8)])


main()
