#!/usr/bin/env python3
"""List "Ask Claude" prompts that need an answer. Used by the scheduled Claude task.

An issue is an Ask if it has the `ask-claude` label or its title starts with "[Ask]".
Each item is either a new prompt (no answer yet) or a follow-up (someone commented
`/followup <question>` after the last answer).

Prints a JSON list to stdout. Needs the GitHub CLI (`gh`).
Usage: python scripts/pending_asks.py [owner/repo]
"""
import json
import os
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
ALLOWED = {a.strip().upper() for a in os.environ.get("ALLOWED_ASSOCIATIONS", "ALL").split(",")}
MAX_PER_RUN = int(os.environ.get("MAX_ASKS_PER_RUN", "10"))


def gh(path: str):
    out = subprocess.run(["gh", "api", path], check=True, capture_output=True, text=True).stdout
    return json.loads(out)


def allowed(assoc: str) -> bool:
    return "ALL" in ALLOWED or (assoc or "").upper() in ALLOWED


def parse_prompt(body: str) -> str:
    """Take the text under '### Prompt' (issue form), or the whole body for a free-form issue."""
    body = body or ""
    m = re.search(r"^###\s+Prompt\s*\n(.*?)(?=^###\s|\Z)", body, flags=re.M | re.S)
    text = (m.group(1) if m else body).strip()
    return "" if text == "_No response_" else text


def is_ask(issue: dict) -> bool:
    labels = {l["name"] for l in issue.get("labels", [])}
    return "ask-claude" in labels or (issue.get("title") or "").lower().startswith("[ask]")


def main() -> None:
    repo = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("GITHUB_REPOSITORY", "prabodhghule/rule-forge")
    issues = gh(f"repos/{repo}/issues?state=open&per_page=100&sort=created&direction=asc")
    work = []
    for issue in issues:
        if issue.get("pull_request") or not is_ask(issue):
            continue
        n = issue["number"]
        f = ROOT / "answers" / f"issue-{n}.json"
        previous = json.loads(f.read_text(encoding="utf-8")) if f.exists() else None
        since = previous["updated_at"] if previous else ""

        followups = []
        if previous and issue.get("comments"):
            for c in gh(f"repos/{repo}/issues/{n}/comments?per_page=100"):
                body = (c.get("body") or "").strip()
                if body.startswith("/followup") and allowed(c.get("author_association")) and c["created_at"] > since:
                    q = body[len("/followup"):].strip()
                    if q:
                        followups.append(q)

        if previous and not followups:
            continue
        if not previous and not allowed(issue.get("author_association")):
            continue
        prompt = parse_prompt(issue.get("body") or "")
        if not previous and not prompt:
            continue

        work.append({
            "issue": n,
            "title": issue["title"],
            "issue_url": issue["html_url"],
            "author": issue["user"]["login"],
            "prompt": "\n\n".join(followups) if previous else prompt,
            "is_followup": bool(previous),
            "history": previous["turns"] if previous else [],
        })
        if len(work) >= MAX_PER_RUN:
            break
    json.dump(work, sys.stdout, indent=2, ensure_ascii=False)
    print()


if __name__ == "__main__":
    main()
