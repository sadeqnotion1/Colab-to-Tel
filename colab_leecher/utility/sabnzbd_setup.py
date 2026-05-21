"""
SABnzbd Setup and Management for Colab Environment

This module handles installation, configuration, and management of SABnzbd
as a backend service for NZB downloading in the Colab environment.
"""

import os
import sys
import subprocess
import time
import json
import configparser
import tempfile
from pathlib import Path
from ..utility.variables import Paths, BOT


class SABnzbdManager:
    """Manages SABnzbd installation and lifecycle in Colab"""

    def __init__(self):
        self.sabnzbd_dir = Path("/content/sabnzbd")
        self.config_dir = self.sabnzbd_dir / "config"
        self.download_dir = Path(Paths.DOWN_PATH)
        self.incomplete_dir = self.sabnzbd_dir / "incomplete"
        self.config_file = self.config_dir / "sabnzbd.ini"

        self.host = "127.0.0.1"
        self.port = 8080
        self.api_key = None
        self.process = None

    def install_sabnzbd(self):
        """Install SABnzbd and dependencies"""
        print("📦 Installing SABnzbd...")

        try:
            # Update package list
            subprocess.run(["apt-get", "update", "-qq"], check=True)

            # Install dependencies
            deps = [
                "python3-dev",
                "par2",
                "unrar",
                "unzip",
                "p7zip-full"
            ]

            subprocess.run(["apt-get", "install", "-y", "-qq"] + deps, check=True)

            # Install SABnzbd via pip
            subprocess.run([
                sys.executable, "-m", "pip", "install",
                "sabnzbd", "--quiet"
            ], check=True)

            print("✅ SABnzbd installed successfully")
            return True

        except subprocess.CalledProcessError as e:
            print(f"❌ Installation failed: {e}")
            return False

    def generate_config(self):
        """Generate SABnzbd configuration from bot credentials"""
        print("⚙️ Generating SABnzbd configuration...")

        # Create directories
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.incomplete_dir.mkdir(parents=True, exist_ok=True)

        # Generate API key
        import secrets
        self.api_key = secrets.token_hex(16)

        # Create configuration
        config = configparser.ConfigParser()

        # Misc settings
        config['misc'] = {
            'host': self.host,
            'port': str(self.port),
            'api_key': self.api_key,
            'username': '',  # No web auth needed in Colab
            'password': '',
            'download_dir': str(self.download_dir),
            'complete_dir': str(self.download_dir),
            'download_free': '20G',  # Reserve 20GB for Colab
            'auto_browser': '0',
            'check_new_rel': '0',
            'auto_disconnect': '1',
            'pre_script': '',
            'post_script': '',
        }

        # Add Usenet servers from bot credentials
        server_count = 0

        if hasattr(BOT.Setting, 'nzb_providers') and BOT.Setting.nzb_providers:
            for name, provider_config in BOT.Setting.nzb_providers.items():
                if not provider_config.get('host'):
                    continue

                connections = provider_config.get('connections', 10)
                if connections == 0:
                    continue

                server_count += 1
                section = f'servers.{server_count}'

                config[section] = {
                    'name': name,
                    'displayname': name,
                    'host': provider_config.get('host', ''),
                    'port': str(provider_config.get('port', 563)),
                    'username': provider_config.get('username', ''),
                    'password': provider_config.get('password', ''),
                    'connections': str(connections),
                    'ssl': '1' if provider_config.get('ssl', True) else '0',
                    'ssl_verify': '2',  # Strict verification
                    'ssl_ciphers': '',
                    'enable': '1',
                    'optional': '0',
                    'retention': '0',
                }

        # Categories
        config['categories'] = {
            'Default': '*',
        }

        # Write config
        with open(self.config_file, 'w') as f:
            config.write(f)

        print(f"✅ Configuration created: {self.config_file}")
        print(f"   API Key: {self.api_key}")
        print(f"   Servers configured: {server_count}")

        return True

    def start_sabnzbd(self):
        """Start SABnzbd daemon"""
        print("🚀 Starting SABnzbd...")

        if not self.config_file.exists():
            print("❌ Configuration file not found. Run generate_config() first.")
            return False

        try:
            # Start SABnzbd in daemon mode
            cmd = [
                "python3", "-m", "sabnzbd",
                "-f", str(self.config_file),
                "-s", f"{self.host}:{self.port}",
                "-d",  # Daemon mode
                "--pidfile", str(self.sabnzbd_dir / "sabnzbd.pid")
            ]

            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )

            # Wait for SABnzbd to start
            print("   Waiting for SABnzbd to start...")
            time.sleep(5)

            # Check if it's running
            if self.is_running():
                print(f"✅ SABnzbd started successfully at http://{self.host}:{self.port}")
                return True
            else:
                print("❌ SABnzbd failed to start")
                return False

        except Exception as e:
            print(f"❌ Failed to start SABnzbd: {e}")
            return False

    def is_running(self):
        """Check if SABnzbd is running"""
        try:
            import requests
            response = requests.get(
                f"http://{self.host}:{self.port}/sabnzbd/api",
                params={"mode": "version", "output": "json"},
                timeout=2
            )
            return response.status_code == 200
        except Exception as check_err:
            print(f"⚠️ SABnzbd health check failed: {check_err}")
            return False

    def stop_sabnzbd(self):
        """Stop SABnzbd daemon"""
        print("🛑 Stopping SABnzbd...")

        try:
            import requests
            requests.get(
                f"http://{self.host}:{self.port}/sabnzbd/api",
                params={"mode": "shutdown", "apikey": self.api_key},
                timeout=5
            )

            if self.process:
                self.process.wait(timeout=10)

            print("✅ SABnzbd stopped")
            return True

        except Exception as e:
            print(f"❌ Failed to stop SABnzbd: {e}")
            return False

    def setup_tunnel(self):
        """Setup cloudflared tunnel to expose SABnzbd web UI"""
        # Check if platform supports tunnel (Linux only)
        import platform
        if platform.system() != 'Linux':
            print(f"⚠️ Tunnel setup skipped (not supported on {platform.system()})")
            print(f"   SABnzbd will be accessible locally at http://{self.host}:{self.port}")
            return None

        print("🌐 Setting up public tunnel for SABnzbd web UI...")

        try:
            cloudflared_pkg_path = Path(tempfile.gettempdir()) / "cloudflared.deb"

            # Install cloudflared
            subprocess.run([
                "wget", "-q",
                "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb",
                "-O", str(cloudflared_pkg_path)
            ], check=True, timeout=30)

            subprocess.run([
                "dpkg", "-i", str(cloudflared_pkg_path)
            ], check=True, capture_output=True)

            try:
                cloudflared_pkg_path.unlink(missing_ok=True)
            except OSError as cleanup_err:
                print(f"⚠️ Could not remove temporary cloudflared package: {cleanup_err}")

            print("✅ Cloudflared installed")

            # Start tunnel in background
            tunnel_log = self.sabnzbd_dir / "tunnel.log"
            tunnel_cmd = [
                "cloudflared", "tunnel",
                "--url", f"http://{self.host}:{self.port}",
                "--logfile", str(tunnel_log)
            ]

            self.tunnel_process = subprocess.Popen(
                tunnel_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )

            # Wait and extract URL from log
            print("   Waiting for tunnel URL...")

            # Try multiple times to extract URL (cloudflared takes time to start)
            import re
            url_patterns = [
                r'https://[a-z0-9-]+\.trycloudflare\.com',
                r'https?://[a-z0-9-]+\.trycloudflare\.com',
                r'(https://.*?\.trycloudflare\.com)',
            ]

            for attempt in range(15):  # Try for up to 15 seconds
                time.sleep(1)

                # Check log file
                if tunnel_log.exists():
                    with open(tunnel_log, 'r') as f:
                        log_content = f.read()

                    for pattern in url_patterns:
                        match = re.search(pattern, log_content)
                        if match:
                            self.tunnel_url = match.group(0)
                            print(f"✅ Public URL: {self.tunnel_url}")
                            print(f"   (Found after {attempt + 1} seconds)")
                            return self.tunnel_url

                # Also check stderr (cloudflared sometimes outputs there)
                if attempt % 3 == 0:  # Check every 3 seconds
                    print(f"   Still waiting... ({attempt + 1}s)")

            # Last attempt - dump log content for debugging
            print("⚠️ Could not extract tunnel URL after 15 seconds")
            if tunnel_log.exists():
                print(f"   Log file exists at: {tunnel_log}")
                with open(tunnel_log, 'r') as f:
                    log_preview = f.read()[:500]
                    print(f"   Log preview: {log_preview}")
            else:
                print(f"   Log file not found: {tunnel_log}")

            return None

        except Exception as e:
            print(f"⚠️ Tunnel setup failed: {e}")
            print("   SABnzbd still accessible locally at http://127.0.0.1:8080")
            return None

    def get_config_info(self):
        """Get configuration info for the bot"""
        config = {
            'host': self.host,
            'port': self.port,
            'api_key': self.api_key,
            'base_url': f"http://{self.host}:{self.port}",
            'download_dir': str(self.download_dir),
            'config_dir': str(self.config_dir)
        }

        if hasattr(self, 'tunnel_url') and self.tunnel_url:
            config['public_url'] = self.tunnel_url

        return config


def setup_sabnzbd(enable_tunnel=True):
    """
    Complete SABnzbd setup for Colab environment

    Args:
        enable_tunnel: If True, creates a public tunnel to access web UI

    Returns:
        dict: Configuration info if successful, None otherwise
    """
    manager = SABnzbdManager()

    # Install
    if not manager.install_sabnzbd():
        return None

    # Configure
    if not manager.generate_config():
        return None

    # Start
    if not manager.start_sabnzbd():
        return None

    # Setup public tunnel (optional)
    if enable_tunnel:
        manager.setup_tunnel()

    # Get config info
    config_info = manager.get_config_info()

    # Save URL to file so bot can send it via Telegram on startup
    # Use public URL if available (tunnel), otherwise use local URL
    try:
        # Get repository root (2 levels up from this file)
        repo_root = Path(__file__).parent.parent.parent
        sabnzbd_info_file = repo_root / '.sabnzbd_url.txt'

        print(f"\n📝 Creating notification file for Telegram...")
        print(f"   Repository root: {repo_root}")
        print(f"   File path: {sabnzbd_info_file}")

        # Prefer public URL, fallback to local URL
        url_to_save = config_info.get('public_url') or config_info.get('base_url')

        print(f"   Public URL: {config_info.get('public_url', 'None')}")
        print(f"   Base URL: {config_info.get('base_url', 'None')}")
        print(f"   URL to save: {url_to_save}")
        print(f"   API Key: {config_info.get('api_key', 'None')[:16]}..." if config_info.get('api_key') else "   API Key: None")

        if url_to_save and config_info.get('api_key'):
            with open(sabnzbd_info_file, 'w') as f:
                f.write(f"{url_to_save}\n")
                f.write(f"{config_info['api_key']}\n")
                # Add a flag to indicate if it's local or public
                f.write(f"{'public' if config_info.get('public_url') else 'local'}\n")

            url_type = "public" if config_info.get('public_url') else "local"

            # Verify file was created
            if sabnzbd_info_file.exists():
                file_size = sabnzbd_info_file.stat().st_size
                print(f"   ✅ File created successfully ({file_size} bytes)")
                print(f"   ✅ Saved {url_type} URL info for Telegram notification")

                # Show file contents for verification
                print(f"\n   File contents:")
                with open(sabnzbd_info_file, 'r') as f:
                    for i, line in enumerate(f, 1):
                        display_line = line.strip()
                        if i == 2 and len(display_line) > 20:  # Hide most of API key
                            display_line = display_line[:16] + "..."
                        print(f"      Line {i}: {display_line}")
            else:
                print(f"   ❌ ERROR: File not found after writing!")
        else:
            print(f"   ❌ ERROR: Missing URL or API key - cannot create file")
            print(f"   This means the bot won't send a Telegram notification")
    except Exception as e:
        print(f"   ❌ ERROR: Could not save URL info file: {e}")
        import traceback
        traceback.print_exc()

    return config_info


if __name__ == "__main__":
    # Quick test
    info = setup_sabnzbd()
    if info:
        print("\n" + "="*50)
        print("SABnzbd Setup Complete!")
        print("="*50)
        print(json.dumps(info, indent=2))
