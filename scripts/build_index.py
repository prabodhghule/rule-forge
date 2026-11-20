#!/usr/bin/env python3
"""Collect every rules/*.json file into docs/data/rules.json for the website."""
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent


def build_index() -> int:
    rules = []
    for f in sorted((ROOT / "rules").glob("*.json")):
        try:
            rules.append(json.loads(f.read_text(encoding="utf-8")))
        except json.JSONDecodeError as exc:
            print(f"Skipping {f.name}: {exc}")
    rules.sort(key=lambda r: r.get("updated_at", ""), reverse=True)
    out = ROOT / "docs" / "data" / "rules.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rules, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Indexed {len(rules)} rule(s) -> {out.relative_to(ROOT)}")
    return len(rules)


if __name__ == "__main__":
    build_index()
