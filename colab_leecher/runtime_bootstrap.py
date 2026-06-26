"""Runtime self-heal for Colab-to-Tel YTDL.

Called ONCE at bot startup from colab_leecher/__init__.py, BEFORE yt-dlp is
ever imported. Ensures - in the environment where the bot actually runs - that:

  * curl_cffi is installed so yt-dlp's impersonation backend exists. Without an
    impersonation backend the signed CDN URLs reject every fragment (HTTP 403).
  * Deno is installed and on PATH, required by yt-dlp's ejs:github JS signature
    solver (remote_components=['ejs:github']).

Important companion fix (in downlader/ytdl.py):
  yt-dlp's *library* API requires the `impersonate` option to be an
  ImpersonateTarget instance, NOT a bare string. Passing a string trips
  `assert isinstance(target, ImpersonateTarget)` in networking/impersonate.py,
  which disables impersonation and causes the 403 storm. The ytdl.py patch
  converts the target with ImpersonateTarget.from_str(); this probe does the
  same so its health check matches the bot's real construction exactly.

Design notes:
  * All probes run in SUBPROCESSES, so this parent process never imports yt-dlp
    or curl_cffi before the (possible) upgrade.
  * Idempotent + fast: if the runtime is already healthy it returns in ~1-2s.
  * Never raises: any failure is logged and the bot continues.
  * Controls:
      CLB_SKIP_RUNTIME_BOOTSTRAP=1  disable entirely
      CLB_RUNTIME_FORCE=1           allow installs on non-Linux (e.g. WSL dev)
      YTDL_IMPERSONATE=<target>     target to probe/use (default "chrome")
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys

BOOTSTRAP_REVISION = "2026.06.26-v3.2"

log = logging.getLogger("colab_leecher.runtime_bootstrap")

DENO_BIN = os.path.expanduser(os.environ.get("DENO_INSTALL", "~/.deno").rstrip("/") + "/bin")

# Faithful probe: builds YoutubeDL exactly like the bot (remote_components +
# an ImpersonateTarget instance) in a child process, so a False result here
# means the bot's real construction would also fail.
_PROBE = (
    "import sys, shutil\n"
    "try:\n"
    "    import yt_dlp\n"
    "    opts = {'quiet': True, 'no_warnings': True, 'remote_components': ['ejs:github']}\n"
    "    try:\n"
    "        from yt_dlp.networking.impersonate import ImpersonateTarget\n"
    "        opts['impersonate'] = ImpersonateTarget.from_str(sys.argv[1])\n"
    "    except Exception:\n"
    "        opts['impersonate'] = sys.argv[1]\n"
    "    yt_dlp.YoutubeDL(opts)\n"
    "    imp = True\n"
    "except Exception:\n"
    "    imp = False\n"
    "print('IMP=%s DENO=%s' % (imp, shutil.which('deno') is not None))\n"
)


def _add_deno_to_path() -> None:
    if os.path.isdir(DENO_BIN) and DENO_BIN not in os.environ.get("PATH", "").split(os.pathsep):
        os.environ["PATH"] = DENO_BIN + os.pathsep + os.environ.get("PATH", "")


def _probe(target: str) -> tuple[bool, bool]:
    try:
        out = subprocess.run(
            [sys.executable, "-c", _PROBE, target],
            capture_output=True, text=True, timeout=120, env=os.environ,
        ).stdout
    except Exception as exc:  # noqa: BLE001
        log.warning("runtime-bootstrap: probe failed: %r", exc)
        return False, False
    return ("IMP=True" in out), ("DENO=True" in out)


def _pip(*args: str) -> None:
    subprocess.run([sys.executable, "-m", "pip", "install", *args], timeout=900, check=False)


def diagnose(target: str | None = None) -> tuple[bool, bool]:
    """Probe (no changes) and log the current state. Returns (impersonate_ok, deno_ok)."""
    target = target or os.environ.get("YTDL_IMPERSONATE", "chrome")
    _add_deno_to_path()
    imp, deno = _probe(target)
    log.info("runtime-bootstrap[%s]: impersonate(%s)=%s deno=%s", BOOTSTRAP_REVISION, target, imp, deno)
    return imp, deno


def ensure_runtime(target: str | None = None) -> bool:
    """Make the YTDL runtime healthy if it isn't. Returns True when ready."""
    if os.environ.get("CLB_SKIP_RUNTIME_BOOTSTRAP") == "1":
        log.info("runtime-bootstrap: disabled via CLB_SKIP_RUNTIME_BOOTSTRAP")
        return False
    if os.environ.get("CLB_RUNTIME_READY") == "1":
        return True

    target = target or os.environ.get("YTDL_IMPERSONATE", "chrome")
    _add_deno_to_path()

    imp, deno = _probe(target)
    if imp and deno:
        os.environ["CLB_RUNTIME_READY"] = "1"
        log.info("runtime-bootstrap[%s]: runtime already healthy (impersonate=%s, deno=ok)", BOOTSTRAP_REVISION, target)
        return True

    if not (sys.platform.startswith("linux") or os.environ.get("CLB_RUNTIME_FORCE") == "1"):
        log.warning(
            "runtime-bootstrap: platform %r is not the bot's runtime; skipping auto-install "
            "(impersonate_ok=%s deno_ok=%s). Run the bot in Colab, or set CLB_RUNTIME_FORCE=1.",
            sys.platform, imp, deno,
        )
        return False

    if not imp:
        # SINGLE prerelease-aware install. Do NOT add a separate stable
        # 'curl_cffi' install afterwards without --pre: it would downgrade and
        # re-break impersonation.
        log.info("runtime-bootstrap[%s]: aligning yt-dlp[default] + curl_cffi (prerelease-aware) ...", BOOTSTRAP_REVISION)
        _pip("-U", "--pre", "yt-dlp[default]", "curl_cffi")

    if not deno:
        log.info("runtime-bootstrap[%s]: installing Deno ...", BOOTSTRAP_REVISION)
        try:
            subprocess.run(
                ["bash", "-lc", "curl -fsSL https://deno.land/install.sh | sh"],
                timeout=900, check=False,
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("runtime-bootstrap: deno install failed: %r", exc)
        _add_deno_to_path()

    imp, deno = _probe(target)
    if imp and deno:
        os.environ["CLB_RUNTIME_READY"] = "1"
        log.info("runtime-bootstrap[%s]: runtime ready (impersonate=%s, deno=ok)", BOOTSTRAP_REVISION, target)
        return True

    log.warning(
        "runtime-bootstrap[%s]: runtime NOT fully ready (impersonate_ok=%s deno_ok=%s); "
        "bot will continue. If impersonate_ok is False, run "
        "`pip show curl_cffi yt-dlp` and share it.",
        BOOTSTRAP_REVISION, imp, deno,
    )
    return False


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    diagnose()
    ok = ensure_runtime()
    print("RUNTIME:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
