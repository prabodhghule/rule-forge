#!/usr/bin/env python3
"""List rule requests that need work. Used by the scheduled Claude task.

Prints a JSON list to stdout. Each item is either a new request (no rule yet) or a
regeneration (a maintainer commented `/regenerate ...` after the rule was last written).

Needs the GitHub CLI (`gh`) with access to the repository.
Usage: python scripts/pending.py [owner/repo]
"""
import json
import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from generate_rule import parse_issue_body  # noqa: E402

ALLOWED = {a.strip().upper() for a in os.environ.get("ALLOWED_ASSOCIATIONS", "OWNER,MEMBER,COLLABORATOR").split(",")}


def gh(path: str):
    out = subprocess.run(["gh", "api", path], check=True, capture_output=True, text=True).stdout
    return json.loads(out)


def allowed(assoc: str) -> bool:
    return "ALL" in ALLOWED or (assoc or "").upper() in ALLOWED


def main() -> None:
    repo = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("GITHUB_REPOSITORY", "prabodhghule/rule-forge")
    issues = gh(f"repos/{repo}/issues?labels=rule-request&state=open&per_page=100")
    work = []
    for issue in issues:
        if issue.get("pull_request"):
            continue
        n = issue["number"]
        rule_file = ROOT / "rules" / f"issue-{n}.json"
        previous = json.loads(rule_file.read_text(encoding="utf-8")) if rule_file.exists() else None
        since = previous["updated_at"] if previous else ""

        feedback, maintainer_ok = "", False
        if issue.get("comments"):
            for c in gh(f"repos/{repo}/issues/{n}/comments?per_page=100"):
                body = (c.get("body") or "").strip()
                if body.startswith("/regenerate") and allowed(c.get("author_association")) and c["created_at"] > since:
                    feedback, maintainer_ok = body[len("/regenerate"):].strip(), True

        if previous and not maintainer_ok:
            continue  # already done, nothing new asked
        if not previous and not (allowed(issue.get("author_association")) or maintainer_ok):
            continue  # outsider request waiting for a maintainer's /regenerate

        work.append({
            "issue": n,
            "title": issue["title"],
            "issue_url": issue["html_url"],
            "author": issue["user"]["login"],
            "request": parse_issue_body(issue.get("body") or ""),
            "feedback": feedback,
            "previous_query": previous["rule"].get("query", "") if previous else "",
        })
    json.dump(work, sys.stdout, indent=2, ensure_ascii=False)
    print()


if __name__ == "__main__":
    main()
