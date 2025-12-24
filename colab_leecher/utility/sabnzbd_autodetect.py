"""
SABnzbd Auto-Detection and Configuration

Automatically detects if SABnzbd is running locally or remotely
and configures the bot to use it.
"""

import requests
import json
from pathlib import Path
from typing import Optional, Dict
from .log import log


def detect_sabnzbd(host: str = "127.0.0.1", port: int = 8080, api_key: str = "") -> Optional[Dict]:
    """
    Detect if SABnzbd is running and get its configuration

    Args:
        host: SABnzbd host
        port: SABnzbd port
        api_key: SABnzbd API key (if known)

    Returns:
        Config dict if SABnzbd is running, None otherwise
    """
    base_url = f"http://{host}:{port}"

    try:
        # Try to connect to SABnzbd API
        response = requests.get(
            f"{base_url}/sabnzbd/api",
            params={"mode": "version", "output": "json", "apikey": api_key},
            timeout=2
        )

        if response.status_code == 200:
            data = response.json()
            version = data.get('version', 'unknown')

            log.info(f"✅ SABnzbd detected at {base_url} (version {version})")

            return {
                'host': host,
                'port': port,
                'api_key': api_key,
                'base_url': base_url,
                'version': version
            }
    except:
        pass

    return None


def load_sabnzbd_config_from_credentials() -> Optional[Dict]:
    """
    Load SABnzbd configuration from credentials.json if available

    Returns:
        SABnzbd config dict or None
    """
    try:
        creds_file = Path(__file__).parent.parent.parent / "credentials.json"

        if creds_file.exists():
            with open(creds_file, 'r') as f:
                creds = json.load(f)

            sabnzbd_config = creds.get('SABNZBD', {})

            if sabnzbd_config:
                host = sabnzbd_config.get('host', '127.0.0.1')
                port = sabnzbd_config.get('port', 8080)
                api_key = sabnzbd_config.get('api_key', '')

                return detect_sabnzbd(host, port, api_key)
    except Exception as e:
        log.warning(f"Could not load SABnzbd config from credentials.json: {e}")

    return None


def auto_configure_sabnzbd() -> Optional[Dict]:
    """
    Auto-configure SABnzbd by:
    1. Checking credentials.json for manual configuration
    2. Detecting SABnzbd on localhost:8080 (default)
    3. Trying common SABnzbd ports

    Returns:
        SABnzbd config dict or None
    """
    log.info("Auto-detecting SABnzbd...")

    # Try credentials.json first
    config = load_sabnzbd_config_from_credentials()
    if config:
        return config

    # Try default localhost:8080
    config = detect_sabnzbd("127.0.0.1", 8080)
    if config:
        return config

    # Try other common ports
    for port in [8085, 9090, 8888]:
        config = detect_sabnzbd("127.0.0.1", port)
        if config:
            return config

    log.info("SABnzbd not detected")
    return None


def create_notification_file(config: Dict, url_type: str = "local"):
    """
    Create .sabnzbd_url.txt for bot to send Telegram notification

    Args:
        config: SABnzbd configuration dict
        url_type: 'local' or 'public'
    """
    try:
        repo_root = Path(__file__).parent.parent.parent
        sabnzbd_info_file = repo_root / '.sabnzbd_url.txt'

        url = config.get('public_url') or config.get('base_url')
        api_key = config.get('api_key', 'N/A')

        if url:
            with open(sabnzbd_info_file, 'w') as f:
                f.write(f"{url}\n")
                f.write(f"{api_key}\n")
                f.write(f"{url_type}\n")

            log.info(f"✅ Created SABnzbd notification file ({url_type})")
            return True
    except Exception as e:
        log.warning(f"Could not create SABnzbd notification file: {e}")

    return False
