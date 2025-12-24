#================================================
#FILE: colab_leecher/downlader/terabox_enhanced.py
#================================================
"""
Enhanced TeraBox Downloader using TeraboxDL package

This module provides improved TeraBox downloading with:
- Cookie-based authentication for reliability
- Progress tracking callbacks
- Automatic fallback to API method
- Better error handling
"""

import logging
import asyncio
from pathlib import Path
from typing import Optional

try:
    from TeraboxDL import TeraboxDL
    TERABOXDL_AVAILABLE = True
except ImportError:
    TERABOXDL_AVAILABLE = False
    logging.warning("TeraboxDL package not available, using fallback method only")

from ..utility.variables import BOT, Paths, TRANSFER, TaskError
from ..utility.helper import status_bar, sizeUnit

log = logging.getLogger(__name__)


class TeraBoxDownloader:
    """
    Enhanced TeraBox downloader using official TeraboxDL package
    Automatically falls back to old API method if needed
    """

    def __init__(self, client, message, task_ctx=None):
        """
        Initialize TeraBox downloader

        Args:
            client: Pyrogram client instance
            message: Telegram message object
            task_ctx: Optional task context for multi-task support
        """
        self.client = client
        self.message = message
        self.task_ctx = task_ctx

        # Get cookie from settings
        self.cookie = BOT.Setting.terabox_cookie if hasattr(BOT.Setting, 'terabox_cookie') else ""

        # Download directory
        if task_ctx:
            self.download_dir = task_ctx.down_path
        else:
            self.download_dir = Paths.down_path

        log.info(f"TeraBox downloader initialized (cookie: {bool(self.cookie)}, TeraboxDL: {TERABOXDL_AVAILABLE})")

    async def download(self, url: str, index: int = 0) -> bool:
        """
        Download file from TeraBox URL with automatic fallback

        Args:
            url: TeraBox share link
            index: Link index for tracking

        Returns:
            bool: True if successful, False otherwise
        """
        # Try enhanced method first if available
        if TERABOXDL_AVAILABLE and self.cookie:
            try:
                return await self._enhanced_download(url, index)
            except Exception as e:
                log.warning(f"Enhanced download failed: {e}, trying fallback")
                return await self._fallback_download(url, index)
        else:
            # Use fallback if no cookie or TeraboxDL not available
            if not TERABOXDL_AVAILABLE:
                log.info("TeraboxDL not available, using API fallback")
            elif not self.cookie:
                log.info("No TeraBox cookie configured, using API fallback")

            return await self._fallback_download(url, index)

    async def _enhanced_download(self, url: str, index: int) -> bool:
        """
        Download using TeraboxDL package (cookie-based)

        Args:
            url: TeraBox share link
            index: Link index for tracking

        Returns:
            bool: True if successful, False otherwise
        """
        log.info(f"[TeraBox Enhanced] Starting download for link {index}")

        try:
            # Initialize TeraboxDL
            terabox = TeraboxDL(self.cookie)

            # Get file info
            log.info(f"[TeraBox Enhanced] Fetching file info...")
            file_info = terabox.get_file_info(url)

            if "error" in file_info:
                raise Exception(f"Failed to get file info: {file_info['error']}")

            filename = file_info.get('file_name', f'terabox_file_{index}')
            file_size = file_info.get('sizebytes', 0)
            file_size_str = sizeUnit(file_size) if file_size else "Unknown"

            log.info(f"[TeraBox Enhanced] File: {filename} ({file_size_str})")

            # Create download path
            download_path = Path(self.download_dir)
            download_path.mkdir(parents=True, exist_ok=True)

            # Download with progress tracking
            log.info(f"[TeraBox Enhanced] Starting download to {download_path}")

            # Run blocking download in executor to not block asyncio
            loop = asyncio.get_event_loop()

            result = await loop.run_in_executor(
                None,
                lambda: terabox.download(
                    file_info,
                    save_path=str(download_path),
                    callback=lambda downloaded, total, pct: self._sync_progress_callback(
                        filename, downloaded, total, pct
                    )
                )
            )

            if "error" in result:
                raise Exception(f"Download failed: {result['error']}")

            # Track successful download
            if TRANSFER:
                TRANSFER.successful_downloads.append({
                    'url': url,
                    'filename': filename,
                    'size': file_size
                })

            log.info(f"[TeraBox Enhanced] Download completed: {filename}")
            return True

        except Exception as e:
            log.error(f"[TeraBox Enhanced] Download error: {e}")

            # Track failure
            if TaskError:
                TaskError.failed_links.append({
                    "link": url,
                    "filename": filename if 'filename' in locals() else "Unknown",
                    "index": index,
                    "reason": f"Enhanced method failed: {str(e)[:100]}"
                })

            raise  # Re-raise to trigger fallback

    def _sync_progress_callback(self, filename, downloaded, total, percentage):
        """
        Synchronous progress callback for TeraboxDL

        Note: This is called from a thread, so we can't directly call async functions
        """
        # Just log progress for now
        # In production, you might want to use a queue to send updates to main thread
        if percentage % 10 == 0:  # Log every 10%
            log.info(f"[TeraBox] {filename}: {percentage:.1f}% ({sizeUnit(downloaded)}/{sizeUnit(total)})")

    async def _fallback_download(self, url: str, index: int) -> bool:
        """
        Fallback to old API-based method

        Uses the current terabox.py implementation

        Args:
            url: TeraBox share link
            index: Link index for tracking

        Returns:
            bool: True if successful, False otherwise
        """
        log.info(f"[TeraBox Fallback] Using API method for link {index}")

        try:
            # Import old method
            from .terabox import terabox_download

            return await terabox_download(url, index, self.task_ctx)

        except Exception as e:
            log.error(f"[TeraBox Fallback] API method also failed: {e}")

            # Track failure
            if TaskError:
                TaskError.failed_links.append({
                    "link": url,
                    "filename": f"terabox_file_{index}",
                    "index": index,
                    "reason": f"Both methods failed: {str(e)[:100]}"
                })

            return False


# Convenience function to maintain compatibility
async def enhanced_terabox_download(link: str, index: int, task_ctx=None, client=None, message=None) -> bool:
    """
    Convenience function for enhanced TeraBox download

    Args:
        link: TeraBox URL
        index: Link index
        task_ctx: Task context
        client: Pyrogram client
        message: Telegram message

    Returns:
        bool: True if successful
    """
    downloader = TeraBoxDownloader(client, message, task_ctx)
    return await downloader.download(link, index)
