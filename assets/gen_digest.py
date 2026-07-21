#!/usr/bin/env python3
"""Auto research digest for the profile README.

Pulls the live notes table from the Neil Quant Labs (quant-research) repo,
figures out (1) the most recent *completed* research note and its finding, and
(2) the next *planned* note ("currently researching"), and injects a compact,
always-current digest into the profile README between the DIGEST markers.

Run daily by a GitHub Action — so when a new note lands in quant-research, the
profile updates itself with zero edits here. Falls back to bundled values if
the repo can't be reached.
"""
from __future__ import annotations

import os
import re
import urllib.request

HERE = os.path.dirname(__file__)
ROOT = os.path.dirname(HERE)
README = os.path.join(ROOT, "README.md")
REPO = "https://github.com/hilothefunnydog123-coder/quant-research"
RAW = "https://raw.githubusercontent.com/hilothefunnydog123-coder/quant-research/main/README.md"

# Used only if the repo can't be fetched (keeps the profile from ever breaking).
FALLBACK = {
    "done_num": "003",
    "done_q": "Momentum vs. mean reversion across regimes, after costs?",
    "done_find": ("Over 4,916 days of SPY, neither beats buy-and-hold (Sharpe 0.63) after costs "
                  "— but each is a regime bet: momentum leads in bull markets, mean reversion "
                  "earns 1.07 in bear markets, then its ~6× turnover lets 5bp costs turn it negative"),
    "next_num": "004",
    "next_q": "How effective are liquidity-grab / FVG setups, statistically?",
}


def _strip_md(s: str) -> str:
    """Turn a markdown table cell into plain text: drop bold/italic, links → text."""
    s = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", s)     # [text](url) -> text
    s = s.replace("**", "").replace("`", "")
    s = re.sub(r"(?<!\w)\*(?!\s)(.+?)(?<!\s)\*(?!\w)", r"\1", s)  # *italic* -> italic
    s = s.replace("📄 PDF", "").replace("·", " ").strip(" —-")
    return re.sub(r"\s+", " ", s).strip()


def parse_notes(md: str):
    """Return list of {num, question, finding, planned} from the notes table."""
    notes = []
    for line in md.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 4:
            continue
        m = re.search(r"\d+", cells[0].replace("*", ""))
        if not m or "---" in cells[0]:
            continue
        finding = cells[2]
        planned = ("planned" in finding.lower()
                   or _strip_md(finding) in ("", "—", "-", "TBD"))
        notes.append({"num": f"{int(m.group()):03d}",
                      "question": _strip_md(cells[1]),
                      "finding": _strip_md(finding),
                      "planned": planned})
    return notes


def get_digest():
    try:
        req = urllib.request.Request(RAW, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=25) as resp:
            md = resp.read().decode("utf-8", "replace")
        notes = parse_notes(md)
        done = [n for n in notes if not n["planned"]]
        planned = [n for n in notes if n["planned"]]
        if not done:
            raise RuntimeError("no completed notes parsed")
        latest = max(done, key=lambda n: n["num"])
        nxt = min(planned, key=lambda n: n["num"]) if planned else None
        print(f"digest: latest {latest['num']}, next {nxt['num'] if nxt else '—'}")
        return {
            "done_num": latest["num"], "done_q": latest["question"],
            "done_find": latest["finding"],
            "next_num": nxt["num"] if nxt else "next",
            "next_q": nxt["question"] if nxt else "an idea worth testing honestly",
        }
    except Exception as exc:
        print(f"digest fetch failed ({exc}); using fallback")
        return FALLBACK


def build_block(d: dict) -> str:
    return f"""<!--DIGEST:START-->
> 🔬 **Latest from [Neil Quant Labs]({REPO}):** **Note {d['done_num']} — {d['done_q']}** → *{d['done_find']}.* &nbsp;[**read the paper →**]({REPO})
>
> 🧫 **Currently researching:** Note {d['next_num']} — *{d['next_q']}*
<!--DIGEST:END-->"""


def inject(block: str) -> None:
    with open(README) as f:
        text = f.read()
    pattern = re.compile(r"<!--DIGEST:START-->.*?<!--DIGEST:END-->", re.DOTALL)
    if pattern.search(text):
        text = pattern.sub(block, text)
    else:
        print("no DIGEST markers in README; skipping injection")
        return
    with open(README, "w") as f:
        f.write(text)


def main() -> None:
    d = get_digest()
    inject(build_block(d))
    print(f"digest updated: latest={d['done_num']}, researching={d['next_num']}")


if __name__ == "__main__":
    main()
