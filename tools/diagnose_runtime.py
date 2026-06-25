#!/usr/bin/env python3
"""Diagnose / gate the Colab-to-Tel YTDL runtime.

Exits 0 ONLY if all of the following hold:
  - yt-dlp imports
  - curl_cffi imports
  - the impersonate target actually initializes (mirrors get_YT_Name /
    _build_ydl_opts, i.e. the exact call that was raising AssertionError)
  - Deno is on PATH (required by the ejs:github signature solver)

Otherwise it prints the failing item(s) and exits 1.

Usage:
    python3 diagnose_runtime.py [--target chrome-124:windows-10]
    (falls back to $YTDL_IMPERSONATE, then "chrome")
"""
import os
import shutil
import subprocess
import sys


def main() -> int:
    target = "chrome"
    args = sys.argv[1:]
    for i, a in enumerate(args):
        if a == "--target" and i + 1 < len(args):
            target = args[i + 1]
    target = os.environ.get("YTDL_IMPERSONATE", target)

    fails = []

    # 1) yt-dlp present (fatal on its own)
    try:
        import yt_dlp
        print(f"[OK]   yt-dlp {yt_dlp.version.__version__}")
    except Exception as e:  # noqa: BLE001
        print(f"[FAIL] yt-dlp not importable: {e!r}")
        print("\nRUNTIME: FAIL -> yt-dlp")
        return 1

    # 2) curl_cffi present (impersonation is impossible without it)
    try:
        import curl_cffi
        print(f"[OK]   curl_cffi {getattr(curl_cffi, '__version__', '?')}")
    except Exception as e:  # noqa: BLE001
        print(f"[FAIL] curl_cffi not importable (impersonation impossible): {e!r}")
        fails.append("curl_cffi")

    # 3) impersonate target actually initializes -- this is the exact call
    #    that was raising 'AssertionError' in your logs.
    try:
        yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "impersonate": target})
        print(f"[OK]   impersonate target {target!r} initializes")
    except Exception as e:  # noqa: BLE001
        print(f"[FAIL] impersonate target {target!r}: {type(e).__name__}: {e}")
        try:
            out = subprocess.run(
                [sys.executable, "-m", "yt_dlp", "--list-impersonate-targets"],
                capture_output=True, text=True, timeout=60,
            ).stdout.strip()
            if out:
                print("       available targets (set YTDL_IMPERSONATE to one of these):")
                for line in out.splitlines()[:8]:
                    print("        ", line)
            else:
                print("       (no impersonate targets available -> curl_cffi <-> yt-dlp mismatch)")
        except Exception:  # noqa: BLE001
            pass
        fails.append("impersonate")

    # 4) Deno on PATH (ejs:github signature solver)
    deno = shutil.which("deno")
    if deno:
        ver = ""
        try:
            ver = subprocess.run(["deno", "--version"], capture_output=True, text=True, timeout=20).stdout.splitlines()[0]
        except Exception:  # noqa: BLE001
            pass
        print(f"[OK]   deno on PATH: {deno}  {ver}")
    else:
        print("[FAIL] deno NOT on PATH (ejs:github signature solver cannot run -> per-fragment 403)")
        print("       if Deno is installed, the BOT PROCESS must inherit it:")
        print("       os.environ['PATH'] = os.environ['PATH'] + ':' + os.path.expanduser('~/.deno/bin')")
        fails.append("deno")

    print()
    if fails:
        print("RUNTIME: FAIL ->", ", ".join(fails))
        return 1
    print("RUNTIME: PASS - impersonation + Deno ready. Safe to start the bot.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
