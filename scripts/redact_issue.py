#!/usr/bin/env python3
"""Rewrite a GitHub issue's title and body with client/sensitive data masked.

Usage: python scripts/redact_issue.py <issue-number> [--term "Client Name" ...] [--repo owner/repo] [--dry-run]

--term adds client or company names to mask. They are used for this run only and never stored.
Prints what kind of data was masked. Exit code 0 even when nothing needed masking.

Note: GitHub keeps an issue's edit history. After this runs, the repo owner should delete
the original revision (issue → "edited" menu → select the first revision → "Delete revision").
"""
import argparse
import json
import pathlib
import subprocess
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from redact import redact  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("issue", type=int)
    ap.add_argument("--term", action="append", default=[])
    ap.add_argument("--repo", default="prabodhghule/rule-forge")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    issue = json.loads(subprocess.run(["gh", "api", f"repos/{a.repo}/issues/{a.issue}"],
                                      check=True, capture_output=True, text=True).stdout)
    title, f1 = redact(issue.get("title") or "", a.term)
    body, f2 = redact(issue.get("body") or "", a.term)
    found = {k: f1.get(k, 0) + f2.get(k, 0) for k in set(f1) | set(f2)}
    if not found:
        print(f"Issue #{a.issue}: nothing sensitive found")
        return 0
    print(f"Issue #{a.issue}: masked {found}")
    if a.dry_run:
        print(body)
        return 0
    body += "\n\n> ⚠️ Client or sensitive details were removed from this request automatically."
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as fh:
        json.dump({"title": title, "body": body}, fh)
    subprocess.run(["gh", "api", "-X", "PATCH", f"repos/{a.repo}/issues/{a.issue}", "--input", fh.name],
                   check=True, capture_output=True)
    print(f"Issue #{a.issue}: updated on GitHub. Delete the original revision from its edit history.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
