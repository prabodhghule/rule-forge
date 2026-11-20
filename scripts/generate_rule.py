#!/usr/bin/env python3
"""Turn a GitHub "rule-request" issue into a detection rule using Claude.

Reads the issue from environment variables (set by the GitHub Action), asks Claude
for a structured rule, saves it to rules/issue-<n>.json, rebuilds the website index
and writes a Markdown comment for the issue.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import pathlib
import re
import sys
import traceback

ROOT = pathlib.Path(__file__).resolve().parent.parent
RULES_DIR = ROOT / "rules"
PROMPT_FILE = ROOT / "prompts" / "system.md"
KNOWLEDGE_DIR = ROOT / "knowledge"
KNOWLEDGE_LIMIT = 60_000

sys.path.insert(0, str(ROOT / "scripts"))
from build_index import build_index  # noqa: E402

# Issue-form headings -> internal keys (matched case-insensitively by prefix).
FIELDS = {
    "query language": "language",
    "data source": "data_source",
    "rule requirement": "requirement",
    "logic": "logic",
    "mitre": "mitre",
    "expected severity": "severity",
    "sample logs": "samples",
}

RULE_TOOL = {
    "name": "submit_rule",
    "description": "Submit the finished detection rule.",
    "input_schema": {
        "type": "object",
        "properties": {
            "rule_name": {"type": "string", "description": "Short, descriptive rule name"},
            "summary": {"type": "string", "description": "One or two sentences on what the rule detects"},
            "query_language": {"type": "string", "description": "e.g. XQL, KQL, SPL, Sigma"},
            "query": {"type": "string", "description": "The complete, ready-to-run query"},
            "logic_explanation": {
                "type": "array", "items": {"type": "string"},
                "description": "Step-by-step explanation of how the query works",
            },
            "assumptions": {
                "type": "array", "items": {"type": "string"},
                "description": "Fields, datasets or behaviour you assumed; anything the requester must verify",
            },
            "false_positives": {"type": "array", "items": {"type": "string"}},
            "tuning": {"type": "array", "items": {"type": "string"}, "description": "How to reduce noise"},
            "mitre": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {"id": {"type": "string"}, "name": {"type": "string"}},
                    "required": ["id", "name"],
                },
            },
            "severity": {"type": "string", "enum": ["Informational", "Low", "Medium", "High", "Critical"]},
            "testing": {"type": "string", "description": "How to safely trigger or validate the rule"},
            "variants": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {"name": {"type": "string"}, "query": {"type": "string"}},
                    "required": ["name", "query"],
                },
            },
        },
        "required": ["rule_name", "summary", "query_language", "query", "logic_explanation", "severity"],
    },
}


def parse_issue_body(body: str) -> dict[str, str]:
    """Parse the Markdown GitHub generates from an issue form (### Heading / value)."""
    result: dict[str, str] = {}
    parts = re.split(r"^###\s+", body or "", flags=re.M)
    for part in parts[1:]:
        heading, _, value = part.partition("\n")
        heading = heading.strip().lower()
        value = value.strip()
        # Strip code fences the form adds around rendered fields.
        fence = re.fullmatch(r"```[\w-]*\n(.*?)\n?```", value, flags=re.S)
        if fence:
            value = fence.group(1).strip()
        if value == "_No response_":
            value = ""
        for prefix, key in FIELDS.items():
            if heading.startswith(prefix):
                result[key] = value
                break
    if not result.get("requirement") and body and not parts[1:]:
        # Free-form issue (no template): treat the whole body as the requirement.
        result["requirement"] = body.strip()
    return result


def load_system_prompt() -> str:
    prompt = PROMPT_FILE.read_text(encoding="utf-8")
    extra, used = [], 0
    if KNOWLEDGE_DIR.is_dir():
        for f in sorted(KNOWLEDGE_DIR.iterdir()):
            if f.name.lower() == "readme.md" or f.suffix.lower() not in {".md", ".txt"}:
                continue
            text = f.read_text(encoding="utf-8", errors="replace")
            room = KNOWLEDGE_LIMIT - used
            if room <= 0:
                break
            text = text[:room]
            used += len(text)
            extra.append(f"### {f.name}\n{text}")
    if extra:
        prompt += "\n\n## Team knowledge (from the repository's knowledge/ folder)\n\n" + "\n\n".join(extra)
    return prompt


def build_user_prompt(title: str, req: dict[str, str], feedback: str, previous: dict | None) -> str:
    language = req.get("language") or "XQL (Cortex XSIAM / XDR)"
    severity = req.get("severity") or "Let Claude decide"
    lines = [
        "Write a detection rule for this request.",
        "<request>",
        f"Title: {title}",
        f"Query language: {language}",
        f"Data source / dataset: {req.get('data_source') or 'not specified'}",
        f"Requirement:\n{req.get('requirement') or 'not specified'}",
        f"Logic / conditions:\n{req.get('logic') or 'none given'}",
        f"MITRE ATT&CK: {req.get('mitre') or 'not specified'}",
        f"Expected severity: {severity}",
        f"Sample logs / fields:\n{req.get('samples') or 'none given'}",
        "</request>",
    ]
    if previous:
        lines += [
            "",
            "A previous version of this rule exists:",
            "<previous_query>",
            previous.get("query", ""),
            "</previous_query>",
        ]
    if feedback:
        lines += ["", "The requester asked for these changes:", "<feedback>", feedback, "</feedback>"]
    return "\n".join(lines)


def call_claude(system: str, user: str, model: str) -> dict:
    import anthropic

    client = anthropic.Anthropic()
    resp = client.messages.create(
        model=model,
        max_tokens=8000,
        system=system,
        tools=[RULE_TOOL],
        tool_choice={"type": "tool", "name": "submit_rule"},
        messages=[{"role": "user", "content": user}],
    )
    for block in resp.content:
        if block.type == "tool_use" and block.name == "submit_rule":
            return dict(block.input)
    raise RuntimeError(f"Claude did not return a rule (stop_reason={resp.stop_reason})")


def fence(text: str) -> str:
    """Pick a code fence longer than any backtick run inside the text."""
    longest = max((len(m) for m in re.findall(r"`+", text)), default=0)
    return "`" * max(3, longest + 1)


def bullets(items) -> str:
    return "\n".join(f"- {i}" for i in items) if items else "_None_"


def comment_markdown(rule: dict, site_url: str) -> str:
    r = rule["rule"]
    q = r.get("query", "")
    f = fence(q)
    lang = (r.get("query_language") or "").split()[0].lower()
    hint = {"xql": "sql", "kql": "kusto", "sigma": "yaml", "spl": "splunk-spl"}.get(lang, "")
    mitre = ", ".join(f"{m['id']} {m['name']}" for m in r.get("mitre") or []) or "_None_"
    parts = [
        f"## {r.get('rule_name', 'Generated rule')}",
        f"**Language:** {r.get('query_language')} · **Severity:** {r.get('severity')} · **Revision:** {rule['revision']}",
        "",
        r.get("summary", ""),
        "",
        f"{f}{hint}\n{q}\n{f}",
        "",
        "### How it works",
        bullets(r.get("logic_explanation")),
        "",
        "### Assumptions to verify",
        bullets(r.get("assumptions")),
        "",
        f"**MITRE ATT&CK:** {mitre}",
        "",
    ]
    if site_url:
        parts.append(f"View it on the Rules page: {site_url}#rule-{rule['issue']}")
    parts.append("\nNeed changes? Comment `/regenerate` followed by what to change.")
    return "\n".join(parts)


def set_output(**kwargs: str) -> None:
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as fh:
            for k, v in kwargs.items():
                fh.write(f"{k}={v}\n")


def write_comment(text: str) -> None:
    path = os.environ.get("COMMENT_FILE", str(ROOT / "comment.md"))
    pathlib.Path(path).write_text(text, encoding="utf-8")


def main() -> int:
    env = os.environ
    issue_no = int(env["ISSUE_NUMBER"])
    title = re.sub(r"^\[Rule\]\s*", "", env.get("ISSUE_TITLE", "")).strip() or f"Rule request #{issue_no}"
    body = env.get("ISSUE_BODY", "")
    comment = env.get("COMMENT_BODY", "").strip()
    association = env.get("AUTHOR_ASSOCIATION", "NONE").upper()
    allowed = [a.strip().upper() for a in (env.get("ALLOWED_ASSOCIATIONS") or "OWNER,MEMBER,COLLABORATOR").split(",")]
    model = env.get("CLAUDE_MODEL") or "claude-sonnet-5-5"

    if "ALL" not in allowed and association not in allowed:
        write_comment(
            "Thanks for the request. To control API costs, rules are only generated automatically for "
            "repository collaborators. A maintainer can comment `/regenerate` to run it."
        )
        set_output(status="skipped")
        return 0

    feedback = comment[len("/regenerate"):].strip() if comment.startswith("/regenerate") else ""
    req = parse_issue_body(body)
    rule_path = RULES_DIR / f"issue-{issue_no}.json"
    previous = json.loads(rule_path.read_text(encoding="utf-8")) if rule_path.exists() else None

    try:
        generated = call_claude(
            load_system_prompt(),
            build_user_prompt(title, req, feedback, previous["rule"] if previous else None),
            model,
        )
    except Exception as exc:  # report the failure on the issue instead of failing silently
        traceback.print_exc()
        write_comment(f"Claude could not generate this rule: `{type(exc).__name__}: {exc}`\n\n"
                      "Fix the problem and comment `/regenerate` to try again.")
        set_output(status="failed")
        return 0

    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    record = {
        "issue": issue_no,
        "issue_url": env.get("ISSUE_URL", ""),
        "title": title,
        "requested_by": env.get("ISSUE_AUTHOR", ""),
        "request": req,
        "created_at": previous["created_at"] if previous else now,
        "updated_at": now,
        "revision": (previous["revision"] + 1) if previous else 1,
        "model": model,
        "last_feedback": feedback,
        "rule": generated,
    }
    RULES_DIR.mkdir(exist_ok=True)
    rule_path.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    build_index()

    write_comment(comment_markdown(record, env.get("SITE_URL", "")))
    set_output(status="generated")
    print(f"Wrote {rule_path.relative_to(ROOT)} (revision {record['revision']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
