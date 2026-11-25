#!/usr/bin/env python3
"""Save an answer written by the scheduled Claude task, rebuild the site index, and
(optionally) comment on and label the issue.

Usage:
  python scripts/save_answer.py --work work-item.json --answer answer.md [--post] [--term NAME ...]

work-item.json  one item from scripts/pending_asks.py
answer.md       Claude's answer in Markdown
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
from redact import redact  # noqa: E402

# Answers may link to public docs (URLs/hosts are allowed), but never carry these.
BLOCKING = {"email", "uuid", "token", "secret", "phone", "card", "aadhaar", "pan", "client"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", required=True)
    ap.add_argument("--answer", required=True)
    ap.add_argument("--post", action="store_true")
    ap.add_argument("--repo", default="prabodhghule/rule-forge")
    ap.add_argument("--term", action="append", default=[], help="client/company name to mask (not stored)")
    a = ap.parse_args()

    work = json.loads(pathlib.Path(a.work).read_text(encoding="utf-8"))
    answer = pathlib.Path(a.answer).read_text(encoding="utf-8").strip()
    if not answer:
        sys.exit("answer.md is empty")

    _, check = redact(answer, a.term)
    blocked = {k: v for k, v in check.items() if k in BLOCKING}
    if blocked:
        sys.exit(f"answer.md contains sensitive data {blocked}. Remove it (use generic placeholders) and retry.")

    prompt, found = redact(work.get("prompt", ""), a.term)
    title, f2 = redact(work.get("title", ""), a.term)
    if found or f2:
        print(f"Masked in stored prompt: {found or f2}")

    n = int(work["issue"])
    path = ROOT / "answers" / f"issue-{n}.json"
    previous = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    turns = (previous["turns"] if previous else []) + [{"prompt": prompt, "answer": answer, "at": now}]
    record = {
        "issue": n,
        "issue_url": work.get("issue_url", ""),
        "title": re.sub(r"^\[Ask\]\s*", "", title, flags=re.I).strip() or f"Question #{n}",
        "asked_by": work.get("author", ""),
        "created_at": previous["created_at"] if previous else now,
        "updated_at": now,
        "turns": turns,
    }
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    build_index()
    print(f"Saved {path.relative_to(ROOT)} ({len(turns)} turn(s))")

    if a.post:
        owner, repo = a.repo.split("/")
        site = f"https://{owner}.github.io/{repo}/ask.html#ask-{n}"
        body = (answer + f"\n\n---\n*Answered by Claude. Also on the [Ask Claude page]({site}). "
                "Comment `/followup <question>` to continue.*")
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as fh:
            fh.write(body)
        subprocess.run(["gh", "api", f"repos/{a.repo}/issues/{n}/comments", "-F", f"body=@{fh.name}"],
                       check=True, capture_output=True)
        subprocess.run(["gh", "label", "create", "answered", "--repo", a.repo, "--color", "2ea043",
                        "--description", "Claude answered this prompt"], capture_output=True)
        subprocess.run(["gh", "api", f"repos/{a.repo}/issues/{n}/labels", "-f", "labels[]=answered"],
                       check=True, capture_output=True)
        print(f"Commented on and labelled issue #{n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
