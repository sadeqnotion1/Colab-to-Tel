"""
SABnzbd Setup Cell for Google Colab

Copy this code to a Colab cell and run it to set up SABnzbd for NZB downloading.
This should be run AFTER installing the bot but BEFORE starting it.
"""

# ============================================================================
# SABnzbd Setup for Colab
# ============================================================================

print("🚀 Setting up SABnzbd for NZB downloads...")
print("=" * 70)

# Step 1: Install SABnzbd and dependencies
print("\n📦 Step 1: Installing SABnzbd...")

import subprocess
import sys

# Install system dependencies
!apt-get update -qq
!apt-get install -y -qq python3-pip python3-dev par2 unrar unzip p7zip-full

# Install SABnzbd via pip
!{sys.executable} -m pip install sabnzbd --quiet

print("✅ SABnzbd installed successfully")

# Step 2: Set up SABnzbd
print("\n⚙️ Step 2: Configuring SABnzbd...")

from colab_leecher.utility.sabnzbd_setup import setup_sabnzbd
from colab_leecher.downlader.sabnzbd_downloader import set_sabnzbd_config

# Run setup with public tunnel enabled
sabnzbd_config = setup_sabnzbd(enable_tunnel=True)

if sabnzbd_config:
    print("✅ SABnzbd configured and started")
    print(f"   Local URL: {sabnzbd_config['base_url']}")
    print(f"   Download Dir: {sabnzbd_config['download_dir']}")

    # Set config for use by bot
    set_sabnzbd_config(sabnzbd_config)

    print("\n" + "=" * 70)
    print("✅ SABnzbd Setup Complete!")
    print("=" * 70)

    # Show public URL prominently if available
    if sabnzbd_config.get('public_url'):
        print("\n🌐 SABnzbd Web UI (Click to open):")
        print(f"   {sabnzbd_config['public_url']}")
        print(f"\n🔑 API Key (for manual access):")
        print(f"   {sabnzbd_config['api_key']}")
    else:
        print("\n📌 IMPORTANT: Save this API key for manual access if needed")
        print(f"   API Key: {sabnzbd_config['api_key']}")

    print("\n🎯 You can now start the bot and use /nzb command")
    print("   The bot will automatically use SABnzbd for all NZB downloads")
    print("=" * 70)

else:
    print("❌ SABnzbd setup failed!")
    print("Check the logs above for errors")
