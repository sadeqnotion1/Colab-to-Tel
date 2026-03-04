#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


def run_cmd(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, text=True, capture_output=True)


def parse_pip_audit_json(payload: str) -> dict | None:
    text = payload.strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find('{"dependencies"')
        if start == -1:
            return None
        candidate = text[start:]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            end = candidate.rfind("}")
            if end == -1:
                return None
            try:
                return json.loads(candidate[: end + 1])
            except json.JSONDecodeError:
                return None


def extract_requirement_names(requirements_path: Path) -> list[str]:
    names: list[str] = []
    pattern = re.compile(r"^\s*([A-Za-z0-9_.-]+)")
    for raw in requirements_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = pattern.match(line)
        if match:
            names.append(match.group(1))
    return names


def build_pinned_requirements(
    requirements_path: Path, report_dir: Path
) -> tuple[Path, list[str], int]:
    freeze_result = run_cmd([sys.executable, "-m", "pip", "freeze"])
    freeze_path = report_dir / "pip-freeze.txt"
    freeze_path.write_text(freeze_result.stdout, encoding="utf-8")

    freeze_map: dict[str, str] = {}
    for line in freeze_result.stdout.splitlines():
        if "==" not in line:
            continue
        name, version = line.split("==", 1)
        freeze_map[name.lower().replace("_", "-")] = version

    names = extract_requirement_names(requirements_path)
    pinned: list[str] = []
    missing: list[str] = []
    for name in names:
        key = name.lower().replace("_", "-")
        if key in freeze_map:
            pinned.append(f"{name}=={freeze_map[key]}")
        else:
            missing.append(name)

    pinned_path = report_dir / "requirements-pinned-audit.txt"
    missing_path = report_dir / "requirements-missing-from-env.txt"
    pinned_path.write_text("\n".join(pinned) + ("\n" if pinned else ""), encoding="utf-8")
    missing_path.write_text(
        "\n".join(missing) + ("\n" if missing else ""), encoding="utf-8"
    )
    return pinned_path, missing, freeze_result.returncode


def summarize_vulns(report: dict) -> tuple[int, int]:
    total = 0
    packages = 0
    for dep in report.get("dependencies", []):
        vulns = dep.get("vulns", [])
        if vulns:
            packages += 1
            total += len(vulns)
    return total, packages


def write_text(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def clear_fallback_artifacts(report_dir: Path) -> None:
    # Keep direct-mode output deterministic by clearing stale fallback files.
    for filename in ("requirements-pinned-audit.txt", "requirements-missing-from-env.txt"):
        artifact_path = report_dir / filename
        if artifact_path.exists():
            artifact_path.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run dependency security audit with Linux-friendly fallback."
    )
    parser.add_argument(
        "--requirements",
        default="requirements.txt",
        help="Path to requirements file (default: requirements.txt)",
    )
    parser.add_argument(
        "--report-dir",
        default="audit/raw/ci",
        help="Directory for raw outputs and summary (default: audit/raw/ci)",
    )
    parser.add_argument(
        "--fail-on-vulns",
        action="store_true",
        help="Return non-zero when vulnerabilities are found.",
    )
    args = parser.parse_args()

    requirements_path = Path(args.requirements).resolve()
    report_dir = Path(args.report_dir).resolve()
    report_dir.mkdir(parents=True, exist_ok=True)

    summary: dict[str, object] = {
        "requirements_path": str(requirements_path),
        "mode": None,
        "direct_returncode": None,
        "fallback_returncode": None,
        "vulnerability_total": 0,
        "packages_with_vulns": 0,
        "missing_from_env": [],
        "execution_error": None,
    }

    direct_cmd = [
        "pip-audit",
        "-r",
        str(requirements_path),
        "-f",
        "json",
        "--progress-spinner",
        "off",
    ]
    direct = run_cmd(direct_cmd)
    write_text(report_dir / "pip-audit-direct.stdout.txt", direct.stdout)
    write_text(report_dir / "pip-audit-direct.stderr.txt", direct.stderr)
    summary["direct_returncode"] = direct.returncode

    direct_report = parse_pip_audit_json(direct.stdout)
    if direct_report and "dependencies" in direct_report:
        total, packages = summarize_vulns(direct_report)
        summary["mode"] = "direct"
        summary["vulnerability_total"] = total
        summary["packages_with_vulns"] = packages
        clear_fallback_artifacts(report_dir)
        write_text(
            report_dir / "pip-audit-report.json",
            json.dumps(direct_report, indent=2),
        )
        write_text(
            report_dir / "dependency-audit-summary.json",
            json.dumps(summary, indent=2),
        )
        if args.fail_on_vulns and total > 0:
            return 1
        return 0

    pinned_path, missing, freeze_rc = build_pinned_requirements(
        requirements_path, report_dir
    )
    summary["missing_from_env"] = missing
    summary["pip_freeze_returncode"] = freeze_rc

    fallback_cmd = [
        "pip-audit",
        "-r",
        str(pinned_path),
        "--no-deps",
        "-f",
        "json",
        "--progress-spinner",
        "off",
    ]
    fallback = run_cmd(fallback_cmd)
    write_text(report_dir / "pip-audit-fallback.stdout.txt", fallback.stdout)
    write_text(report_dir / "pip-audit-fallback.stderr.txt", fallback.stderr)
    summary["fallback_returncode"] = fallback.returncode

    fallback_report = parse_pip_audit_json(fallback.stdout)
    if fallback_report and "dependencies" in fallback_report:
        total, packages = summarize_vulns(fallback_report)
        summary["mode"] = "fallback-no-deps"
        summary["vulnerability_total"] = total
        summary["packages_with_vulns"] = packages
        write_text(
            report_dir / "pip-audit-report.json",
            json.dumps(fallback_report, indent=2),
        )
        write_text(
            report_dir / "dependency-audit-summary.json",
            json.dumps(summary, indent=2),
        )
        if args.fail_on_vulns and total > 0:
            return 1
        return 0

    summary["mode"] = "failed"
    summary["execution_error"] = (
        "Unable to parse pip-audit JSON output in both direct and fallback modes."
    )
    write_text(
        report_dir / "dependency-audit-summary.json",
        json.dumps(summary, indent=2),
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
