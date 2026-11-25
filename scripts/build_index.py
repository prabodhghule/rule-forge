#!/usr/bin/env python3
"""Collect rules/*.json into docs/data/rules.json and answers/*.json into docs/data/answers.json."""
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _collect(src: str, dest: str) -> int:
    items = []
    for f in sorted((ROOT / src).glob("*.json")):
        try:
            items.append(json.loads(f.read_text(encoding="utf-8")))
        except json.JSONDecodeError as exc:
            print(f"Skipping {f.name}: {exc}")
    items.sort(key=lambda r: r.get("updated_at", ""), reverse=True)
    out = ROOT / "docs" / "data" / dest
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(items, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Indexed {len(items)} item(s) -> {out.relative_to(ROOT)}")
    return len(items)


def build_index() -> int:
    n = _collect("rules", "rules.json")
    _collect("answers", "answers.json")
    return n


if __name__ == "__main__":
    build_index()
