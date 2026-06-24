"""
Enhanced Status and Progress Display
Beautiful, modern progress tracking for downloads/uploads
"""

import os
from .bar_style import BAR_STYLE  # M2: single source of truth
from typing import Dict, Any, List
from datetime import datetime
from .ui_components import (
    Box, Emoji, ProgressBar, TimeFormatter, SizeFormatter, MessageTemplate
)
from .keyboard_layouts import ProgressKeyboards


class StatusDisplay:
    """Enhanced stateless status message builder"""

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def speed_emoji(bytes_per_second: float) -> str:
        """Return a colored dot based on current speed tier."""
        mb = bytes_per_second / (1024 * 1024)
        if mb >= 10:
            return "\U0001f7e2"   # Fast  (>= 10 MB/s)
        elif mb >= 3:
            return "\U0001f7e1"   # Medium (3-10 MB/s)
        elif mb >= 0.5:
            return "\U0001f7e0"   # Slow  (0.5-3 MB/s)
        else:
            return "\U0001f534"   # Very slow (< 0.5 MB/s)

    @staticmethod
    def smart_eta(seconds: float, downloaded: int = 0) -> str:
        """Format ETA with a warm-up phase for very early estimates.
        
        This treats the 512KB warm-up logic strictly as a visual mapping.
        """
        if downloaded < 1024 * 512:          # < 512 KB transferred
            return "\u23f3 Warming up..."
        if seconds is None or seconds < 0 or seconds > 86400 * 7:
            return "Calculating..."
        return TimeFormatter.format_eta(seconds)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @classmethod
    def download_status(
        cls,
        filename: str,
        progress: float,
        speed: float,
        downloaded: int,
        total_size: int,
        elapsed_time: float,
        task_id: str = None,
        eta: float = None,
        engine: str = None,
        style: str = "sleek"
    ) -> "tuple[str, Any]":
        """
        Create download status message.

        Styles:  sleek (default) | modern | compact | classic
        Returns: (message_text, keyboard)
        """
        if style == "sleek":
            return cls._sleek_status(
                operation="DOWNLOADING",
                op_emoji=Emoji.DOWNLOAD,
                filename=filename,
                progress=progress,
                speed=speed,
                done=downloaded,
                total=total_size,
                eta=eta,
                elapsed_time=elapsed_time,
                task_id=task_id,
                engine=engine
            )
        elif style == "modern":
            return cls._modern_download_status(
                filename=filename,
                progress=progress,
                speed=speed,
                downloaded=downloaded,
                total_size=total_size,
                eta=eta,
                elapsed_time=elapsed_time,
                task_id=task_id,
                engine=engine
            )
        elif style == "compact":
            return cls._compact_status(
                operation="DOWNLOADING",
                filename=filename,
                progress=progress,
                speed=speed,
                done=downloaded,
                total=total_size,
                eta=eta,
                elapsed_time=elapsed_time,
                task_id=task_id,
                engine=engine
            )
        else:
            return cls._classic_status(
                header=f"{Emoji.DOWNLOAD} DOWNLOADING",
                filename=filename,
                progress=progress,
                speed=speed,
                done=downloaded,
                total=total_size,
                eta=eta,
                elapsed_time=elapsed_time,
                task_id=task_id,
                engine=engine
            )

    @classmethod
    def upload_status(
        cls,
        filename: str,
        progress: float,
        speed: float,
        uploaded: int,
        total_size: int,
        elapsed_time: float,
        task_id: str = None,
        eta: float = None,
        destination: str = "Telegram",
        style: str = "sleek"
    ) -> "tuple[str, Any]":
        """
        Create upload status message.

        Styles:  sleek (default) | modern
        Returns: (message_text, keyboard)
        """
        if style == "sleek":
            return cls._sleek_status(
                operation=f"UPLOADING -> {destination.upper()}",
                op_emoji=Emoji.UPLOAD,
                filename=filename,
                progress=progress,
                speed=speed,
                done=uploaded,
                total=total_size,
                eta=eta,
                elapsed_time=elapsed_time,
                task_id=task_id,
                engine=None
            )
        return cls._modern_upload_status(
            filename=filename,
            progress=progress,
            speed=speed,
            uploaded=uploaded,
            total_size=total_size,
            eta=eta,
            elapsed_time=elapsed_time,
            task_id=task_id,
            destination=destination
        )

    @classmethod
    def processing_status(
        cls,
        filename: str,
        operation: str,
        elapsed_time: float,
        task_id: str = None,
        progress: float = None,
        current_file: str = None,
        files_done: int = None,
        total_files: int = None
    ) -> "tuple[str, Any]":
        """Create processing/extracting status"""
        lines = [f"<b>{Emoji.PROCESS} {operation.upper()}</b>\n"]
        lines.append(
            f"{Box.TOP_LEFT}{Emoji.TAG} <b>Name:</b> <code>{filename}</code>")

        if progress is not None:
            bar = ProgressBar.generate(progress, 12, BAR_STYLE)
            lines.append(f"{Box.MIDDLE_LEFT}[{bar}] <b>{progress:.1f}%</b>")

        if current_file:
            lines.append(
                f"{Box.MIDDLE_LEFT}{Emoji.DOCUMENT} <b>Current:</b> <code>{current_file}</code>")

        if files_done is not None and total_files is not None:
            lines.append(
                f"{Box.MIDDLE_LEFT}{Emoji.ARCHIVE} <b>Files:</b> {files_done}/{total_files}")

        elapsed_str = TimeFormatter.format_seconds(elapsed_time)
        lines.append(
            f"{Box.BOTTOM_LEFT}{Emoji.TIME} <b>Elapsed:</b> {elapsed_str}")

        message = "\n".join(lines)
        keyboard = ProgressKeyboards.processing(task_id, operation)
        return message, keyboard

    # ------------------------------------------------------------------
    # Sleek style  <- NEW default
    # ------------------------------------------------------------------

    @classmethod
    def _sleek_status(
        cls,
        operation: str,
        op_emoji: str,
        filename: str,
        progress: float,
        speed: float,
        done: int,
        total: int,
        eta: float,
        elapsed_time: float,
        task_id: str = None,
        engine: str = None
    ) -> "tuple[str, Any]":
        """
        Clean, scan-friendly layout. One dense block - no box-drawing noise.

        Example output:
        📥 DOWNLOADING
        filename.mkv

        ██████████▒░░░  73.4%

        🟢 45.2 MB/s   ⏳ 12s   ⏱ 1m 4s
        💾 3.20 GB / 4.37 GB
        """
        bar = ProgressBar.generate(progress, 15, BAR_STYLE)
        speed_dot = cls.speed_emoji(speed)
        speed_str = SizeFormatter.format_speed(speed) if speed > 0 else "--"
        eta_str = cls.smart_eta(eta, done)
        elapsed_str = TimeFormatter.format_seconds(elapsed_time)
        done_str = SizeFormatter.format_bytes(done)
        total_str = SizeFormatter.format_bytes(total)

        msg = (
            f"<b>{op_emoji} {operation}</b>\n"
            f"<code>{filename}</code>\n\n"
            f"<b>{bar}</b>  <b>{progress:.1f}%</b>\n\n"
            f"{speed_dot} <b>{speed_str}</b>  "
            f"\u23f3 <b>{eta_str}</b>  \u23f1 <b>{elapsed_str}</b>\n"
            f"\U0001f4be <code>{done_str}</code> / <code>{total_str}</code>"
        )

        if engine:
            msg += f"\n\u2699\ufe0f <i>{engine}</i>"

        keyboard = ProgressKeyboards.downloading(task_id)
        return msg, keyboard

    # ------------------------------------------------------------------
    # Modern style
    # ------------------------------------------------------------------

    @classmethod
    def _modern_download_status(
        cls,
        filename: str,
        progress: float,
        speed: float,
        downloaded: int,
        total_size: int,
        eta: float,
        elapsed_time: float,
        task_id: str = None,
        engine: str = None
    ) -> "tuple[str, Any]":
        """Modern box-drawing download status (gradient bar)."""
        lines = [
            f"<b>{Emoji.DOWNLOAD} DOWNLOADING</b>\n",
            f"{Box.TOP_LEFT}{Emoji.TAG} <b>Name:</b> <code>{filename}</code>",
        ]

        bar = ProgressBar.generate(progress, 14, BAR_STYLE)
        lines.append(f"{Box.MIDDLE_LEFT}[{bar}] <b>{progress:.1f}%</b>")

        if speed > 0:
            speed_dot = cls.speed_emoji(speed)
            speed_str = SizeFormatter.format_speed(speed)
            lines.append(
                f"{Box.MIDDLE_LEFT}{speed_dot} <b>Speed:</b> {speed_str}")

        downloaded_str = SizeFormatter.format_bytes(downloaded)
        total_str = SizeFormatter.format_bytes(total_size)
        lines.append(
            f"{Box.MIDDLE_LEFT}{Emoji.SIZE} <b>Progress:</b> {downloaded_str} / {total_str}")

        if eta is not None and eta > 0:
            eta_str = cls.smart_eta(eta, downloaded)
            lines.append(f"{Box.MIDDLE_LEFT}{Emoji.ETA} <b>ETA:</b> {eta_str}")

        elapsed_str = TimeFormatter.format_seconds(elapsed_time)
        lines.append(
            f"{Box.MIDDLE_LEFT}{Emoji.TIME} <b>Elapsed:</b> {elapsed_str}")

        if engine:
            lines.append(
                f"{Box.BOTTOM_LEFT}{Emoji.PROCESS} <b>Engine:</b> {engine}")
        else:
            lines[-1] = lines[-1].replace(Box.MIDDLE_LEFT, Box.BOTTOM_LEFT, 1)

        message = "\n".join(lines)
        keyboard = ProgressKeyboards.downloading(task_id)
        return message, keyboard

    @classmethod
    def _modern_upload_status(
        cls,
        filename: str,
        progress: float,
        speed: float,
        uploaded: int,
        total_size: int,
        eta: float,
        elapsed_time: float,
        task_id: str = None,
        destination: str = "Telegram"
    ) -> "tuple[str, Any]":
        """Modern box-drawing upload status (gradient bar)."""
        lines = [
            f"<b>{Emoji.UPLOAD} UPLOADING TO {destination.upper()}</b>\n",
            f"{Box.TOP_LEFT}{Emoji.TAG} <b>Name:</b> <code>{filename}</code>",
        ]

        bar = ProgressBar.generate(progress, 14, BAR_STYLE)
        lines.append(f"{Box.MIDDLE_LEFT}[{bar}] <b>{progress:.1f}%</b>")

        if speed > 0:
            speed_dot = cls.speed_emoji(speed)
            speed_str = SizeFormatter.format_speed(speed)
            lines.append(
                f"{Box.MIDDLE_LEFT}{speed_dot} <b>Speed:</b> {speed_str}")

        uploaded_str = SizeFormatter.format_bytes(uploaded)
        total_str = SizeFormatter.format_bytes(total_size)
        lines.append(
            f"{Box.MIDDLE_LEFT}{Emoji.SIZE} <b>Progress:</b> {uploaded_str} / {total_str}")

        if eta is not None and eta > 0:
            eta_str = cls.smart_eta(eta, uploaded)
            lines.append(f"{Box.MIDDLE_LEFT}{Emoji.ETA} <b>ETA:</b> {eta_str}")

        elapsed_str = TimeFormatter.format_seconds(elapsed_time)
        lines.append(
            f"{Box.BOTTOM_LEFT}{Emoji.TIME} <b>Elapsed:</b> {elapsed_str}")

        message = "\n".join(lines)
        keyboard = ProgressKeyboards.uploading(task_id)
        return message, keyboard

    # ------------------------------------------------------------------
    # Compact style
    # ------------------------------------------------------------------

    @classmethod
    def _compact_status(
        cls,
        operation: str,
        filename: str,
        progress: float,
        speed: float,
        done: int,
        total: int,
        eta: float,
        elapsed_time: float,
        task_id: str = None,
        engine: str = None
    ) -> "tuple[str, Any]":
        """Compact style - saves vertical space."""
        bar = ProgressBar.generate(progress, 12, BAR_STYLE)
        speed_dot = cls.speed_emoji(speed)
        speed_str = SizeFormatter.format_speed(speed) if speed > 0 else "--"
        eta_str = cls.smart_eta(eta, done)
        elapsed_str = TimeFormatter.format_seconds(elapsed_time)
        done_str = SizeFormatter.format_bytes(done)
        total_str = SizeFormatter.format_bytes(total)

        message = (
            f"<b>{Emoji.ROCKET} {operation}</b>\n\n"
            f"<code>{filename}</code>\n\n"
            f"[{bar}] <b>{progress:.1f}%</b>\n"
            f"{speed_dot} {speed_str}  {Emoji.ETA} {eta_str}  {Emoji.TIME} {elapsed_str}\n"
            f"{Emoji.SIZE} {done_str}/{total_str}"
        )

        if engine:
            message += f"  {Emoji.PROCESS} {engine}"

        keyboard = ProgressKeyboards.downloading(task_id)
        return message, keyboard

    # ------------------------------------------------------------------
    # Classic style  (HTML/Markdown mix FIXED)
    # ------------------------------------------------------------------

    @classmethod
    def _classic_status(
        cls,
        header: str,
        filename: str,
        progress: float,
        speed: float,
        done: int,
        total: int,
        eta: float,
        elapsed_time: float,
        task_id: str = None,
        engine: str = None
    ) -> "tuple[str, Any]":
        """Classic style - all formatting in HTML (no broken __markdown__ mix)."""
        bar = ProgressBar.generate(progress, 12, BAR_STYLE)
        message = f"<b>{header}</b>\n\n"
        message += f"<b>\U0001f3f7\ufe0f Name >> </b><code>{filename}</code>\n\n"
        message += f"\u256d[{bar}] <b>>></b> <i>{progress:.1f}%</i>\n"

        if speed > 0:
            speed_dot = cls.speed_emoji(speed)
            message += (
                f"\u251c{speed_dot} <b>Speed >></b> "
                f"<b>{SizeFormatter.format_speed(speed)}</b>\n"
            )

        if engine:
            message += f"\u251c{Emoji.PROCESS} <b>Engine >></b> <b>{engine}</b>\n"

        if eta:
            message += (
                f"\u251c{Emoji.ETA} <b>ETA >></b> "
                f"<i>{cls.smart_eta(eta, done)}</i>\n"
            )

        elapsed_str = TimeFormatter.format_seconds(elapsed_time)
        message += (
            f"\u251c{Emoji.TIME} <b>Elapsed >></b> "
            f"<i>{elapsed_str}</i>\n"
        )
        message += f"\u251c\u2705 <b>Done >></b> <b>{SizeFormatter.format_bytes(done)}</b>\n"
        message += f"\u2570{Emoji.ARCHIVE} <b>Total >></b> <b>{SizeFormatter.format_bytes(total)}</b>"

        keyboard = ProgressKeyboards.downloading(task_id)
        return message, keyboard


# ======================================================================
# Completion Messages
# ======================================================================

class CompletionMessage:
    """Generate completion/success messages"""

    @staticmethod
    def download_complete(
        filename: str,
        size: int,
        duration: float,
        engine: str = None,
        file_count: int = 1
    ) -> str:
        """Create download completion message"""
        summary = {
            "File": filename,
            "Size": SizeFormatter.format_bytes(size),
            "Time Taken": TimeFormatter.format_seconds(duration),
        }

        if file_count > 1:
            summary["Files"] = str(file_count)

        if engine:
            summary["Engine"] = engine

        return MessageTemplate.success_message(
            "Download Complete",
            summary,
            show_hashtag=True
        )

    @staticmethod
    def upload_complete(
        files: List[str],
        total_size: int,
        duration: float,
        destination: str = "Telegram",
        links: List[str] = None
    ) -> str:
        """Create upload completion message"""
        file_count = len(files)

        summary = {
            "Files Uploaded": f"{file_count} file{'s' if file_count != 1 else ''}",
            "Total Size": SizeFormatter.format_bytes(total_size),
            "Destination": destination,
            "Time Taken": TimeFormatter.format_seconds(duration),
        }

        message = MessageTemplate.success_message(
            "Upload Complete",
            summary,
            show_hashtag=True
        )

        if links:
            message += "\n\n<b>\U0001f4ce Links:</b>"
            for i, (file, link) in enumerate(zip(files, links), 1):
                message += f"\n{i}. <a href='{link}'>{file}</a>"

        return message

    @staticmethod
    def task_complete(
        title: str,
        details: Dict[str, str],
        hashtag: str = None
    ) -> str:
        """Generic task completion message"""
        if hashtag:
            title = f"{hashtag} {title}"

        return MessageTemplate.success_message(
            title,
            details,
            show_hashtag=bool(hashtag)
        )


# ======================================================================
# Error Messages
# ======================================================================

class ErrorMessage:
    """Generate error messages"""

    @staticmethod
    def download_failed(
        filename: str,
        error: str,
        details: str = None,
        task_id: str = None
    ) -> str:
        """Create download error message"""
        solution = "Please check the URL and try again."

        if "network" in error.lower() or "timeout" in error.lower():
            solution = "Please check your internet connection and try again."
        elif "permission" in error.lower() or "forbidden" in error.lower():
            solution = "The file may be private or require authentication."
        elif "not found" in error.lower():
            solution = "The file or URL was not found. Please verify the link."

        return MessageTemplate.error_message(
            f"Download Failed: {filename}",
            error,
            details,
            solution
        )

    @staticmethod
    def upload_failed(
        filename: str,
        error: str,
        details: str = None
    ) -> str:
        """Create upload error message"""
        solution = "Please try uploading again."

        if "size" in error.lower() or "large" in error.lower():
            solution = "The file may be too large. Try splitting it or using compression."
        elif "timeout" in error.lower():
            solution = "Upload timed out. Try again with a better connection."

        return MessageTemplate.error_message(
            f"Upload Failed: {filename}",
            error,
            details,
            solution
        )

    @staticmethod
    def task_failed(
        task_name: str,
        error: str,
        details: str = None,
        solution: str = None
    ) -> str:
        """Generic task error message"""
        return MessageTemplate.error_message(
            f"Task Failed: {task_name}",
            error,
            details,
            solution or "Please try again or contact support."
        )


# ======================================================================
# Info Messages
# ======================================================================

class InfoMessage:
    """Generate informational messages"""

    @staticmethod
    def task_started(
        task_name: str,
        details: Dict[str, str] = None
    ) -> str:
        """Task started message"""
        lines = [f"<b>{Emoji.ROCKET} {task_name} Started</b>\n"]

        if details:
            for i, (key, value) in enumerate(details.items()):
                prefix = Box.TOP_LEFT if i == 0 else Box.MIDDLE_LEFT
                if i == len(details) - 1:
                    prefix = Box.BOTTOM_LEFT
                lines.append(f"{prefix}{Emoji.BULLET} <b>{key}:</b> {value}")

        return "\n".join(lines)

    @staticmethod
    def task_queued(task_name: str, position: int = None) -> str:
        """Task queued message"""
        msg = f"<b>{Emoji.LOADING} Task Queued</b>\n\n"
        msg += f"{Emoji.TAG} <b>Task:</b> {task_name}\n"

        if position:
            msg += f"{Emoji.INFO} <b>Position in queue:</b> #{position}"
        else:
            msg += f"{Emoji.INFO} Task will start shortly..."

        return msg

    @staticmethod
    def please_wait(message: str = "Processing your request...") -> str:
        """Please wait message"""
        return f"{Emoji.LOADING} <i>{message}</i>"


# ======================================================================
# Convenience functions
# ======================================================================

def create_download_status(
    filename: str,
    progress: float,
    speed: float,
    downloaded: int,
    total_size: int,
    elapsed_time: float = 0.0,
    eta: float = None,
    engine: str = None,
    task_id: str = None,
    style: str = "sleek"
) -> "tuple[str, Any]":
    """Quick download status creation"""
    return StatusDisplay.download_status(
        filename=filename,
        progress=progress,
        speed=speed,
        downloaded=downloaded,
        total_size=total_size,
        elapsed_time=elapsed_time,
        task_id=task_id,
        eta=eta,
        engine=engine,
        style=style
    )


def create_upload_status(
    filename: str,
    progress: float,
    speed: float,
    uploaded: int,
    total_size: int,
    elapsed_time: float = 0.0,
    eta: float = None,
    destination: str = "Telegram",
    task_id: str = None,
    style: str = "sleek"
) -> "tuple[str, Any]":
    """Quick upload status creation"""
    return StatusDisplay.upload_status(
        filename=filename,
        progress=progress,
        speed=speed,
        uploaded=uploaded,
        total_size=total_size,
        elapsed_time=elapsed_time,
        task_id=task_id,
        eta=eta,
        destination=destination,
        style=style
    )
