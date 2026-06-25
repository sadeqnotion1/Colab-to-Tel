#!/usr/bin/env bash
# Hardened runtime fix for Colab-to-Tel YTDL 403s (v2).
#
# Root cause confirmed from the 2026-06-25 run + local repro:
#   * curl_cffi <-> yt-dlp version mismatch => impersonate target "chrome"
#     is unavailable => YoutubeDL() init raises AssertionError => every
#     request falls back to a plain client => CDN 403s every fragment.
#   * the ejs:github signature solver needs Deno, which was not on the
#     bot process PATH.
#
# This script ALIGNS yt-dlp + curl_cffi, installs Deno, and then VERIFIES
# both before exiting 0. If verification fails it exits 1 -- turning the
# previous silent gap into a hard failure.
#
# Usage:
#   bash setup_runtime.sh           # install + verify
#   bash setup_runtime.sh --check   # verify only (no install)
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="${PYTHON:-python3}"
DENO_DIR="${DENO_INSTALL:-$HOME/.deno}"
export PATH="$DENO_DIR/bin:$PATH"

CHECK_ONLY=0
case "${1:-}" in
	--check|--verify-only) CHECK_ONLY=1 ;;
	-h|--help) echo "Usage: $0 [--check]"; exit 0 ;;
	"") ;;
	*) echo "Unknown arg: $1"; echo "Usage: $0 [--check]"; exit 2 ;;
esac

if [ "$CHECK_ONLY" -eq 0 ]; then
	echo "==> [1/3] Aligning yt-dlp[default] + curl_cffi ..."
	"$PY" -m pip install -U --pre "yt-dlp[default]" curl_cffi || { echo "pip update failed"; exit 1; }

	echo "==> [2/3] Force-reinstalling curl_cffi (breaks the version mismatch) ..."
	"$PY" -m pip install -U --force-reinstall --no-deps curl_cffi || { echo "curl_cffi reinstall failed"; exit 1; }

	if command -v deno >/dev/null 2>&1; then
		echo "==> [3/3] Deno already present: $(command -v deno)"
	else
		echo "==> [3/3] Installing Deno ..."
		curl -fsSL https://deno.land/install.sh | sh || { echo "Deno install failed"; exit 1; }
	fi
	export PATH="$DENO_DIR/bin:$PATH"
fi

echo
echo "==> Verifying runtime (hard gate) ..."
"$PY" "$HERE/diagnose_runtime.py" --target "${YTDL_IMPERSONATE:-chrome}"
rc=$?

if [ "$rc" -ne 0 ]; then
	echo
	echo "setup_runtime: FAILED verification. Do NOT start the bot yet."
	echo "If Deno was just installed, make sure the BOT PROCESS inherits PATH:"
	echo "  export PATH=\"$DENO_DIR/bin:\$PATH\""
	echo "  Colab launch cell: os.environ['PATH'] = os.path.expanduser('~/.deno/bin') + ':' + os.environ['PATH']"
	exit "$rc"
fi

echo
echo "setup_runtime: PASS. Restart the bot (and ensure it inherits the PATH above)."
