#!/usr/bin/env python3
from __future__ import annotations

import fnmatch
import subprocess
import sys


EXACT_BLOCKLIST = {
    "credentials.json",
    ".env",
    ".env.local",
}

GLOB_BLOCKLIST = (
    "*.session",
    "*.session-journal",
    "*.token",
    "*.cookie",
    "*.pickle",
)

ALLOWED_EXCEPTIONS = {
    "credentials.json.example",
}


def get_tracked_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files"], capture_output=True, text=True, check=True
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def is_blocked(path: str) -> bool:
    lowered = path.lower().replace("\\", "/")
    basename = lowered.rsplit("/", 1)[-1]

    if basename in ALLOWED_EXCEPTIONS:
        return False
    if basename in EXACT_BLOCKLIST:
        return True
    return any(fnmatch.fnmatch(basename, pattern) for pattern in GLOB_BLOCKLIST)


def main() -> int:
    violations = [path for path in get_tracked_files() if is_blocked(path)]
    if not violations:
        print("No blocked sensitive files are tracked.")
        return 0

    print("Blocked sensitive files are tracked in git:")
    for path in violations:
        print(f" - {path}")
    print("\nRemove these files from tracking before commit.")
    print("Example: git rm --cached <path>")
    return 1


if __name__ == "__main__":
    sys.exit(main())
