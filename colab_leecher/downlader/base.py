# copyright 2025 © theSadeQ | https://github.com/theSadeQ/Telegram-Leecher

"""
Base Downloader Class
Provides common functionality for all downloaders including progress tracking
"""

import time
import logging
from typing import Optional
from pyrogram.types import Message

from colab_leecher.utility.variables import Paths, MSG
from colab_leecher.utility.helper import status_bar, getTime
from colab_leecher.utility.task_context import TaskContext

log = logging.getLogger(__name__)


class BaseDownloader:
    """
    Base class for all downloaders with common functionality

    Provides:
    - Progress tracking variables
    - Standard progress bar updates
    - Task context management
    - Download directory management
    """

    def __init__(self, client, message: Message, task_ctx: TaskContext = None):
        """
        Initialize base downloader

        Args:
            client: Pyrogram client instance
            message: Message that triggered the download
            task_ctx: Optional task context for parallel downloads
        """
        self.client = client
        self.message = message
        self.task_ctx = task_ctx

        # Use task-specific download directory if task_ctx provided, otherwise global
        if task_ctx:
            self.download_dir = task_ctx.down_path
        else:
            self.download_dir = Paths.down_path  # Fallback to global for backward compat

        # Progress tracking variables
        self.download_start_time = 0
        self.current_percentage = 0.0
        self.current_stream_type = ""
        self.total_size = 0
        self.total_downloaded = 0

    async def update_progress_bar(
        self,
        percentage: float,
        status_text: str = "Downloading...",
        speed: str = "N/A",
        eta: str = None,
        engine: str = None
    ):
        """
        Update progress bar using the bot's standard status_bar system

        Args:
            percentage: Download percentage (0-100)
            status_text: Status message (e.g., "Downloading...", "Complete ✅")
            speed: Download speed string (e.g., "5.2 MB/s") or "N/A"
            eta: ETA string or None (will auto-calculate if None)
            engine: Downloader engine name (e.g., "Mindvalley (N_m3u8DL-RE)")
        """
        try:
            # Use task_ctx.status_msg if available, otherwise fall back to global MSG
            status_msg = self.task_ctx.status_msg if self.task_ctx else MSG.status_msg
            if not status_msg:
                return

            # Update current percentage
            self.current_percentage = percentage

            # Calculate elapsed time
            elapsed = time.time() - self.download_start_time if self.download_start_time > 0 else 0

            # Calculate ETA if not provided
            if eta is None:
                if percentage > 0 and percentage < 100 and elapsed > 0:
                    eta_seconds = (elapsed / percentage) * (100 - percentage)
                    eta = getTime(eta_seconds)
                else:
                    eta = "N/A"

            # Default engine name if not provided
            if engine is None:
                engine = self.__class__.__name__.replace("Downloader", "")

            # Create status header with task ID if available
            task_id_str = f" [{self.task_ctx.get_short_id()}]" if self.task_ctx else ""

            # Default stream emoji
            stream_emoji = {"video": "🎬", "audio": "🔊", "subtitle": "📝"}.get(
                self.current_stream_type, "⬇️"
            )

            # Build status header
            status_head = f"<b>{stream_emoji} {engine} Download{task_id_str} »</b>\n\n"
            if self.current_stream_type:
                status_head += f"<b>🎯 Stream » </b><code>{self.current_stream_type.capitalize()}</code>\n"

            # Calculate total size string
            if self.total_size > 0:
                from colab_leecher.utility.helper import sizeUnit
                total_size_str = sizeUnit(self.total_size)
            else:
                total_size_str = "Unknown"

            # Use the standard status_bar function
            await status_bar(
                down_msg=status_head,
                speed=speed,
                percentage=percentage,
                eta=eta,
                done=status_text,
                total_size=total_size_str,
                engine=engine,
                task_ctx=self.task_ctx  # Pass task context for multi-task support
            )

        except Exception as e:
            log.warning(f"Failed to update progress bar: {e}")

    def start_progress_tracking(self, stream_type: str = ""):
        """
        Initialize progress tracking for a new download

        Args:
            stream_type: Type of stream being downloaded (video, audio, subtitle, etc.)
        """
        self.download_start_time = time.time()
        self.current_percentage = 0.0
        self.current_stream_type = stream_type
        self.total_downloaded = 0

    def reset_progress(self):
        """Reset all progress tracking variables"""
        self.download_start_time = 0
        self.current_percentage = 0.0
        self.current_stream_type = ""
        self.total_size = 0
        self.total_downloaded = 0
