"""
SABnzbd setup helper for Google Colab.

This module is Python-syntax-safe so it can be imported and linted in CI,
while still performing the same setup actions when executed.
"""

from __future__ import annotations

import os
import subprocess
import sys


def _run_cmd(cmd: list[str]) -> None:
    """Run a command and raise if it fails."""
    subprocess.run(cmd, check=True)


def setup_sabnzbd_for_colab() -> bool:
    """Install and configure SABnzbd for Colab-based NZB workflows."""
    print("Setting up SABnzbd for NZB downloads...")
    print("=" * 70)

    print("\nStep 1: Installing SABnzbd...")
    _run_cmd(["apt-get", "update", "-qq"])
    _run_cmd(
        [
            "apt-get",
            "install",
            "-y",
            "-qq",
            "python3-dev",
            "par2",
            "unrar",
            "unzip",
            "p7zip-full",
        ]
    )
    _run_cmd([sys.executable, "-m", "pip", "install", "sabnzbd", "--quiet"])
    print("SABnzbd installed successfully")

    print("\nStep 2: Configuring SABnzbd...")
    from colab_leecher.downlader.sabnzbd_downloader import set_sabnzbd_config
    from colab_leecher.utility.sabnzbd_setup import setup_sabnzbd

    sabnzbd_config = setup_sabnzbd(enable_tunnel=True)
    if not sabnzbd_config:
        print("SABnzbd setup failed")
        return False

    print("SABnzbd configured and started")
    print(f"   Local URL: {sabnzbd_config['base_url']}")
    print(f"   Download Dir: {sabnzbd_config['download_dir']}")
    set_sabnzbd_config(sabnzbd_config)

    sabnzbd_info_file = os.path.join(os.getcwd(), ".sabnzbd_url.txt")
    url_to_save = sabnzbd_config.get("public_url") or sabnzbd_config.get("base_url")
    if url_to_save:
        with open(sabnzbd_info_file, "w", encoding="utf-8") as file_handle:
            file_handle.write(f"{url_to_save}\n")
            file_handle.write(f"{sabnzbd_config['api_key']}\n")
            file_handle.write(
                f"{'public' if sabnzbd_config.get('public_url') else 'local'}\n"
            )

    if sabnzbd_config.get("public_url"):
        print("\nSABnzbd Web UI (Public):")
        print(f"   {sabnzbd_config['public_url']}")
    else:
        print("\nSABnzbd Web UI (Local):")
        print(f"   {sabnzbd_config.get('base_url', 'N/A')}")

    print(f"\nAPI Key: {sabnzbd_config['api_key']}")
    print("\nSABnzbd setup complete")
    print("=" * 70)
    return True


if __name__ == "__main__":
    setup_sabnzbd_for_colab()
