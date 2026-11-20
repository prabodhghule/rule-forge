#!/usr/bin/env python3
"""Save a rule written by the scheduled Claude task, rebuild the site index, and
(optionally) comment on and label the issue.

Usage:
  python scripts/save_rule.py --work work-item.json --rule rule.json [--post] [--repo owner/repo]

work-item.json  one item from scripts/pending.py
rule.json       the rule, with the same fields as the submit_rule schema in generate_rule.py
"""
import argparse
import datetime as dt
import json
import pathlib
import re
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from build_index import build_index  # noqa: E402
from generate_rule import RULE_TOOL, comment_markdown  # noqa: E402
from redact import redact, redact_obj  # noqa: E402

# Data kinds that must never appear in a published rule (IPs only warn: queries may use generic ranges).
BLOCKING = {"url", "email", "host", "uuid", "token", "secret", "phone", "card", "aadhaar", "pan", "client"}

REQUIRED = RULE_TOOL["input_schema"]["required"]
SEVERITIES = RULE_TOOL["input_schema"]["properties"]["severity"]["enum"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", required=True)
    ap.add_argument("--rule", required=True)
    ap.add_argument("--post", action="store_true", help="comment on and label the issue with gh")
    ap.add_argument("--repo", default="prabodhghule/rule-forge")
    ap.add_argument("--model", default="Claude (scheduled task)")
    ap.add_argument("--term", action="append", default=[], help="client/company name to mask (not stored)")
    a = ap.parse_args()

    work = json.loads(pathlib.Path(a.work).read_text(encoding="utf-8"))
    rule = json.loads(pathlib.Path(a.rule).read_text(encoding="utf-8"))

    # 1. Mask sensitive data in everything we store from the request.
    found: dict = {}
    work["title"] = redact_obj(work.get("title", ""), a.term, found)
    work["request"] = redact_obj(work.get("request", {}), a.term, found)
    work["feedback"] = redact_obj(work.get("feedback", ""), a.term, found)
    if found:
        print(f"Masked in stored request: {found}")

    # 2. The rule itself must not carry client data.
    check: dict = {}
    redact_obj(rule, a.term, check)
    blocked = {k: v for k, v in check.items() if k in BLOCKING}
    if blocked:
        sys.exit(f"rule.json contains sensitive data {blocked}. Remove client names, hosts, URLs, IDs and tokens, then retry.")
    if check:
        print(f"Warning: rule.json contains {check}. Make sure these are generic values, not client data.")

    missing = [k for k in REQUIRED if not rule.get(k)]
    if missing:
        sys.exit(f"rule.json is missing required fields: {', '.join(missing)}")
    if rule["severity"] not in SEVERITIES:
        sys.exit(f"severity must be one of {SEVERITIES}")
    for key in ("logic_explanation", "assumptions", "false_positives", "tuning", "mitre", "variants"):
        if key in rule and not isinstance(rule[key], list):
            sys.exit(f"{key} must be a list")

    n = int(work["issue"])
    path = ROOT / "rules" / f"issue-{n}.json"
    previous = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    record = {
        "issue": n,
        "issue_url": work.get("issue_url", ""),
        "title": re.sub(r"^\[Rule\]\s*", "", work.get("title", "")).strip() or f"Rule request #{n}",
        "requested_by": work.get("author", ""),
        "request": work.get("request", {}),
        "created_at": previous["created_at"] if previous else now,
        "updated_at": now,
        "revision": previous["revision"] + 1 if previous else 1,
        "model": a.model,
        "last_feedback": work.get("feedback", ""),
        "rule": rule,
    }
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    build_index()
    print(f"Saved {path.relative_to(ROOT)} (revision {record['revision']})")

    if a.post:
        owner, repo = a.repo.split("/")
        site = f"https://{owner}.github.io/{repo}/"
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as fh:
            fh.write(comment_markdown(record, site))
        subprocess.run(["gh", "api", f"repos/{a.repo}/issues/{n}/comments", "-F", f"body=@{fh.name}"],
                       check=True, capture_output=True)
        subprocess.run(["gh", "api", f"repos/{a.repo}/issues/{n}/labels", "-f", "labels[]=rule-generated"],
                       check=True, capture_output=True)
        print(f"Commented on and labelled issue #{n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
