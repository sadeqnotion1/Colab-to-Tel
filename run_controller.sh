#!/usr/bin/env bash
# Thin launcher — leecher + controller bots (one process).
set -e
cd "$(dirname "$0")"
exec python3 -m colab_leecher.run_with_controller
