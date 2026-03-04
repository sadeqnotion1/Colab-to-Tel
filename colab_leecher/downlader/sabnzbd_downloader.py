"""
SABnzbd-based NZB Downloader

⚠️ DEVELOPMENT MODE - NOT PRODUCTION READY ⚠️
This module is currently under active development and may contain bugs.
Use at your own risk - features are experimental and subject to change.

Uses SABnzbd as backend for reliable NZB downloading with progress tracking
and integration with Telegram bot frontend.
"""

import os
import time
import asyncio
import logging
from pathlib import Path
from typing import Optional, Tuple, List

log = logging.getLogger(__name__)

from ..utility.helper import status_bar, sizeUnit
from ..utility.variables import MSG, BOT
from ..utility.sabnzbd_client import SABnzbdClient


class SABnzbdDownloader:
    """NZB downloader using SABnzbd backend"""

    def __init__(self, client, message, sabnzbd_config: dict):
        """
        Initialize SABnzbd downloader

        Args:
            client: Pyrogram client
            message: Telegram message
            sabnzbd_config: SABnzbd configuration dict from setup
        """
        self.client = client
        self.message = message
        self.download_start_time = 0

        # SABnzbd client
        self.sab_client = SABnzbdClient(
            host=sabnzbd_config.get('host', '127.0.0.1'),
            port=sabnzbd_config.get('port', 8080),
            api_key=sabnzbd_config['api_key']
        )

        # Download state
        self.nzo_id = None
        self.current_filename = ""
        self.total_size = 0
        self.last_update_time = 0

    async def update_progress_bar(self, percentage: float, status_text: str = "Downloading...",
                                   speed: str = "N/A", eta: str = "N/A"):
        """
        Update Telegram progress bar

        Args:
            percentage: Progress percentage (0-100)
            status_text: Current status description
            speed: Download speed
            eta: Estimated time remaining
        """
        try:
            if not MSG.status_msg:
                return

            # Throttle updates (every 3 seconds)
            current_time = time.time()
            if current_time - self.last_update_time < 3:
                return

            self.last_update_time = current_time

            # Calculate elapsed time
            elapsed = current_time - self.download_start_time
            elapsed_str = time.strftime('%M:%S', time.gmtime(elapsed))

            # Create status header
            status_head = (
                f"<b>📦 NZB Download (SABnzbd) »</b>\n\n"
                f"<b>📄 File » </b><code>{self.current_filename}</code>\n"
            )

            # Use standard status_bar function
            await status_bar(
                down_msg=status_head,
                speed=speed,
                percentage=percentage,
                eta=eta if eta != "unknown" else "N/A",
                done=status_text,
                total_size=sizeUnit(self.total_size) if self.total_size > 0 else "Unknown",
                engine="SABnzbd"
            )

        except Exception as e:
            log.warning(f"Failed to update progress bar: {e}")

    async def download_nzb(self, nzb_path: str, download_dir: str) -> Tuple[bool, Optional[List[str]]]:
        """
        Download NZB using SABnzbd

        Args:
            nzb_path: Path to .nzb file
            download_dir: Directory to save downloaded files

        Returns:
            Tuple of (success, list of downloaded file paths or None)
        """
        try:
            log.info("=" * 50)
            log.info("Starting SABnzbd-based NZB download")
            log.info("=" * 50)

            self.download_start_time = time.time()

            # Verify SABnzbd is running
            if not self.sab_client.is_alive():
                await self.update_progress_bar(0, "❌ SABnzbd not running")
                log.error("SABnzbd is not running")
                return False, None

            version = self.sab_client.get_version()
            log.info(f"SABnzbd version: {version}")

            # Submit NZB to SABnzbd
            await self.update_progress_bar(0, "Submitting NZB to SABnzbd...")
            success, result = self.sab_client.add_nzb_file(nzb_path, category="Default", priority=1)

            if not success:
                await self.update_progress_bar(0, f"❌ Failed to submit: {result}")
                log.error(f"Failed to submit NZB: {result}")
                return False, None

            self.nzo_id = result
            log.info(f"NZB submitted successfully, ID: {self.nzo_id}")

            # Monitor download progress
            await self.update_progress_bar(1, "Download started...")

            while True:
                # Get download status
                status = self.sab_client.get_download_status(self.nzo_id)

                if not status:
                    await self.update_progress_bar(0, "❌ Download not found")
                    log.error("Download disappeared from queue/history")
                    return False, None

                # Update current filename
                self.current_filename = status.get('name', 'Unknown')

                # Check status
                if status['status'] == 'downloading':
                    # Still downloading
                    percentage = float(status.get('percentage', 0))
                    speed = status.get('speed', 'N/A')
                    eta = status.get('eta', 'N/A')

                    # Parse size
                    size_str = status.get('size', '0')
                    try:
                        # SABnzbd returns size like "1.5 GB"
                        if 'GB' in size_str:
                            self.total_size = int(float(size_str.split()[0]) * 1024 * 1024 * 1024)
                        elif 'MB' in size_str:
                            self.total_size = int(float(size_str.split()[0]) * 1024 * 1024)
                        elif 'KB' in size_str:
                            self.total_size = int(float(size_str.split()[0]) * 1024)
                    except (ValueError, IndexError) as parse_err:
                        log.debug(f"Could not parse SABnzbd size value '{size_str}': {parse_err}")

                    await self.update_progress_bar(
                        percentage,
                        f"Downloading... {percentage:.1f}%",
                        speed=speed,
                        eta=eta
                    )

                    log.debug(f"Progress: {percentage:.1f}%, Speed: {speed}, ETA: {eta}")

                    # Wait before next check
                    await asyncio.sleep(3)

                elif status['status'] == 'Completed':
                    # Download complete!
                    storage_path = status.get('storage', '')
                    log.info(f"Download completed: {storage_path}")

                    # Get downloaded files
                    downloaded_files = []
                    if storage_path and os.path.exists(storage_path):
                        # SABnzbd downloads to a folder
                        if os.path.isdir(storage_path):
                            for root, dirs, files in os.walk(storage_path):
                                for file in files:
                                    file_path = os.path.join(root, file)
                                    downloaded_files.append(file_path)
                                    log.info(f"  Downloaded: {file}")
                        else:
                            downloaded_files.append(storage_path)

                    total_size = sum(os.path.getsize(f) for f in downloaded_files)

                    await self.update_progress_bar(
                        100.0,
                        f"Complete ✅ {sizeUnit(total_size)}"
                    )

                    log.info("=" * 50)
                    log.info("SABnzbd Download Complete")
                    log.info(f"Files: {len(downloaded_files)}")
                    log.info(f"Total Size: {sizeUnit(total_size)}")
                    log.info("=" * 50)

                    return True, downloaded_files

                else:
                    # Failed or other terminal state
                    fail_msg = status.get('fail_message', status['status'])
                    await self.update_progress_bar(0, f"❌ {fail_msg}")
                    log.error(f"Download failed: {fail_msg}")
                    return False, None

        except Exception as e:
            log.exception(f"SABnzbd download failed: {e}")
            await self.update_progress_bar(0, f"❌ Error: {str(e)[:50]}")
            return False, None

    async def cancel_download(self):
        """Cancel current download"""
        if self.nzo_id:
            log.info(f"Canceling download: {self.nzo_id}")
            self.sab_client.delete_download(self.nzo_id, delete_files=True)


# Global SABnzbd configuration (set during initialization)
SABNZBD_CONFIG = None


def set_sabnzbd_config(config: dict):
    """Set SABnzbd configuration for use by downloaders"""
    global SABNZBD_CONFIG
    SABNZBD_CONFIG = config


def get_sabnzbd_config() -> Optional[dict]:
    """Get SABnzbd configuration"""
    return SABNZBD_CONFIG
