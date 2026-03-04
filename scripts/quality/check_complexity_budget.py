#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class FGradeItem:
    file: str
    type: str
    name: str
    complexity: int

    @property
    def key(self) -> tuple[str, str, str]:
        return (self.file, self.type, self.name)


def _normalize_path(path: str) -> str:
    return path.replace("\\", "/")


def run_radon(target: str) -> dict:
    cmd = ["radon", "cc", target, "-j"]
    result = subprocess.run(cmd, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        print("Complexity check failed: radon command error.", file=sys.stderr)
        if result.stdout.strip():
            print(result.stdout.strip(), file=sys.stderr)
        if result.stderr.strip():
            print(result.stderr.strip(), file=sys.stderr)
        raise SystemExit(2)

    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        print("Complexity check failed: invalid JSON from radon.", file=sys.stderr)
        print(str(exc), file=sys.stderr)
        raise SystemExit(2) from exc


def extract_f_grades(radon_payload: dict) -> tuple[list[FGradeItem], dict[str, str]]:
    items: list[FGradeItem] = []
    parse_errors: dict[str, str] = {}

    for file_name, blocks in radon_payload.items():
        if isinstance(blocks, dict):
            err = blocks.get("error")
            if err:
                parse_errors[_normalize_path(file_name)] = str(err)
            continue
        if not isinstance(blocks, list):
            continue
        for block in blocks:
            if not isinstance(block, dict):
                continue
            if block.get("rank") != "F":
                continue
            items.append(
                FGradeItem(
                    file=_normalize_path(file_name),
                    type=str(block.get("type", "unknown")),
                    name=str(block.get("name", "unknown")),
                    complexity=int(block.get("complexity", 0)),
                )
            )

    items.sort(key=lambda i: (i.file, i.type, i.name))
    return items, parse_errors


def write_baseline(path: Path, target: str, items: list[FGradeItem]) -> None:
    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "target": target,
        "entries": [
            {
                "file": item.file,
                "type": item.type,
                "name": item.name,
                "max_complexity": item.complexity,
            }
            for item in items
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def load_baseline(path: Path) -> dict[tuple[str, str, str], int]:
    if not path.exists():
        print(
            f"Complexity baseline is missing: {path}. Run with --update-baseline first.",
            file=sys.stderr,
        )
        raise SystemExit(2)

    data = json.loads(path.read_text(encoding="utf-8"))
    baseline: dict[tuple[str, str, str], int] = {}
    for entry in data.get("entries", []):
        key = (
            _normalize_path(str(entry["file"])),
            str(entry["type"]),
            str(entry["name"]),
        )
        baseline[key] = int(entry["max_complexity"])
    return baseline


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fail on new F-grade complexity blocks or regressions above baseline."
    )
    parser.add_argument("--target", default="colab_leecher")
    parser.add_argument(
        "--baseline", default="audit/complexity-f-baseline.json"
    )
    parser.add_argument("--update-baseline", action="store_true")
    args = parser.parse_args()

    baseline_path = Path(args.baseline).resolve()
    radon_payload = run_radon(args.target)
    current_items, parse_errors = extract_f_grades(radon_payload)

    if parse_errors:
        print("Complexity check failed: radon parse errors detected.", file=sys.stderr)
        for file_name, err in sorted(parse_errors.items()):
            print(f"- {file_name}: {err}", file=sys.stderr)
        return 1

    if args.update_baseline:
        write_baseline(baseline_path, args.target, current_items)
        print(
            f"Complexity baseline updated: {baseline_path} ({len(current_items)} F-grade entries)."
        )
        return 0

    baseline = load_baseline(baseline_path)
    current = {item.key: item.complexity for item in current_items}

    new_f = sorted(k for k in current if k not in baseline)
    regressions = sorted(
        (k, current[k], baseline[k])
        for k in current
        if k in baseline and current[k] > baseline[k]
    )

    print(f"Complexity F-grade baseline entries: {len(baseline)}")
    print(f"Complexity F-grade current entries: {len(current)}")

    if new_f:
        print("New F-grade blocks detected:", file=sys.stderr)
        for file_name, item_type, name in new_f:
            print(
                f"- {file_name}::{item_type}::{name} (complexity={current[(file_name, item_type, name)]})",
                file=sys.stderr,
            )

    if regressions:
        print("F-grade complexity regressions detected:", file=sys.stderr)
        for (file_name, item_type, name), current_cc, baseline_cc in regressions:
            print(
                f"- {file_name}::{item_type}::{name}: {baseline_cc} -> {current_cc}",
                file=sys.stderr,
            )

    if new_f or regressions:
        return 1

    print("Complexity budget check passed (no new/regressed F-grade blocks).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
