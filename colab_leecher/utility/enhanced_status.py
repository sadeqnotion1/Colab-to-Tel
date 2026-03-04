"""
Enhanced Status and Progress Display
Beautiful, modern progress tracking for downloads/uploads
"""

from typing import Dict, Any, List
from datetime import datetime
from .ui_components import (
    Box, Emoji, ProgressBar, TimeFormatter, SizeFormatter, MessageTemplate
)
from .keyboard_layouts import ProgressKeyboards


class StatusDisplay:
    """Enhanced status message builder"""

    def __init__(self, title: str, task_id: str = None):
        self.title = title
        self.task_id = task_id
        self.start_time = datetime.now()

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
        """Format ETA with a warm-up phase for very early estimates."""
        if downloaded < 1024 * 512:          # < 512 KB transferred
            return "\u23f3 Warming up..."
        if seconds is None or seconds < 0 or seconds > 86400 * 7:
            return "Calculating..."
        return TimeFormatter.format_eta(seconds)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def download_status(
        self,
        filename: str,
        progress: float,
        speed: float,
        downloaded: int,
        total_size: int,
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
            return self._sleek_status(
                "DOWNLOADING", Emoji.DOWNLOAD,
                filename, progress, speed, downloaded, total_size, eta, engine
            )
        elif style == "modern":
            return self._modern_download_status(
                filename, progress, speed, downloaded, total_size, eta, engine
            )
        elif style == "compact":
            return self._compact_status(
                "DOWNLOADING",
                filename, progress, speed, downloaded, total_size, eta, engine
            )
        else:
            return self._classic_status(
                "\U0001f4e5 DOWNLOADING",
                filename, progress, speed, downloaded, total_size, eta, engine
            )

    def upload_status(
        self,
        filename: str,
        progress: float,
        speed: float,
        uploaded: int,
        total_size: int,
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
            return self._sleek_status(
                f"UPLOADING -> {destination.upper()}", Emoji.UPLOAD,
                filename, progress, speed, uploaded, total_size, eta, None
            )
        return self._modern_upload_status(
            filename, progress, speed, uploaded, total_size, eta, destination
        )

    def processing_status(
        self,
        filename: str,
        operation: str,
        progress: float = None,
        current_file: str = None,
        files_done: int = None,
        total_files: int = None
    ) -> "tuple[str, Any]":
        """Create processing/extracting status"""
        elapsed = (datetime.now() - self.start_time).total_seconds()

        lines = [f"<b>{Emoji.PROCESS} {operation.upper()}</b>\n"]
        lines.append(
            f"{Box.TOP_LEFT}{Emoji.TAG} <b>Name:</b> <code>{filename}</code>")

        if progress is not None:
            bar = ProgressBar.generate(progress, 12, "gradient")
            lines.append(f"{Box.MIDDLE_LEFT}[{bar}] <b>{progress:.1f}%</b>")

        if current_file:
            lines.append(
                f"{Box.MIDDLE_LEFT}{Emoji.DOCUMENT} <b>Current:</b> <code>{current_file}</code>")

        if files_done is not None and total_files is not None:
            lines.append(
                f"{Box.MIDDLE_LEFT}{Emoji.ARCHIVE} <b>Files:</b> {files_done}/{total_files}")

        elapsed_str = TimeFormatter.format_seconds(elapsed)
        lines.append(
            f"{Box.BOTTOM_LEFT}{Emoji.TIME} <b>Elapsed:</b> {elapsed_str}")

        message = "\n".join(lines)
        keyboard = ProgressKeyboards.processing(self.task_id, operation)
        return message, keyboard

    # ------------------------------------------------------------------
    # Sleek style  <- NEW default
    # ------------------------------------------------------------------

    def _sleek_status(
        self,
        operation: str,
        op_emoji: str,
        filename: str,
        progress: float,
        speed: float,
        done: int,
        total: int,
        eta: float,
        engine: str
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
        elapsed = (datetime.now() - self.start_time).total_seconds()

        bar = ProgressBar.generate(progress, 15, "gradient")
        speed_dot = self.speed_emoji(speed)
        speed_str = SizeFormatter.format_speed(speed) if speed > 0 else "--"
        eta_str = self.smart_eta(eta, done)
        elapsed_str = TimeFormatter.format_seconds(elapsed)
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

        keyboard = ProgressKeyboards.downloading(self.task_id)
        return msg, keyboard

    # ------------------------------------------------------------------
    # Modern style
    # ------------------------------------------------------------------

    def _modern_download_status(
        self,
        filename: str,
        progress: float,
        speed: float,
        downloaded: int,
        total_size: int,
        eta: float,
        engine: str
    ) -> "tuple[str, Any]":
        """Modern box-drawing download status (gradient bar)."""
        elapsed = (datetime.now() - self.start_time).total_seconds()

        lines = [
            f"<b>{Emoji.DOWNLOAD} DOWNLOADING</b>\n",
            f"{Box.TOP_LEFT}{Emoji.TAG} <b>Name:</b> <code>{filename}</code>",
        ]

        bar = ProgressBar.generate(progress, 14, "gradient")
        lines.append(f"{Box.MIDDLE_LEFT}[{bar}] <b>{progress:.1f}%</b>")

        if speed > 0:
            speed_dot = self.speed_emoji(speed)
            speed_str = SizeFormatter.format_speed(speed)
            lines.append(
                f"{Box.MIDDLE_LEFT}{speed_dot} <b>Speed:</b> {speed_str}")

        downloaded_str = SizeFormatter.format_bytes(downloaded)
        total_str = SizeFormatter.format_bytes(total_size)
        lines.append(
            f"{Box.MIDDLE_LEFT}{Emoji.SIZE} <b>Progress:</b> {downloaded_str} / {total_str}")

        if eta is not None and eta > 0:
            eta_str = self.smart_eta(eta, downloaded)
            lines.append(f"{Box.MIDDLE_LEFT}{Emoji.ETA} <b>ETA:</b> {eta_str}")

        elapsed_str = TimeFormatter.format_seconds(elapsed)
        lines.append(
            f"{Box.MIDDLE_LEFT}{Emoji.TIME} <b>Elapsed:</b> {elapsed_str}")

        if engine:
            lines.append(
                f"{Box.BOTTOM_LEFT}{Emoji.PROCESS} <b>Engine:</b> {engine}")
        else:
            lines[-1] = lines[-1].replace(Box.MIDDLE_LEFT, Box.BOTTOM_LEFT, 1)

        message = "\n".join(lines)
        keyboard = ProgressKeyboards.downloading(self.task_id)
        return message, keyboard

    def _modern_upload_status(
        self,
        filename: str,
        progress: float,
        speed: float,
        uploaded: int,
        total_size: int,
        eta: float,
        destination: str
    ) -> "tuple[str, Any]":
        """Modern box-drawing upload status (gradient bar)."""
        elapsed = (datetime.now() - self.start_time).total_seconds()

        lines = [
            f"<b>{Emoji.UPLOAD} UPLOADING TO {destination.upper()}</b>\n",
            f"{Box.TOP_LEFT}{Emoji.TAG} <b>Name:</b> <code>{filename}</code>",
        ]

        bar = ProgressBar.generate(progress, 14, "gradient")
        lines.append(f"{Box.MIDDLE_LEFT}[{bar}] <b>{progress:.1f}%</b>")

        if speed > 0:
            speed_dot = self.speed_emoji(speed)
            speed_str = SizeFormatter.format_speed(speed)
            lines.append(
                f"{Box.MIDDLE_LEFT}{speed_dot} <b>Speed:</b> {speed_str}")

        uploaded_str = SizeFormatter.format_bytes(uploaded)
        total_str = SizeFormatter.format_bytes(total_size)
        lines.append(
            f"{Box.MIDDLE_LEFT}{Emoji.SIZE} <b>Progress:</b> {uploaded_str} / {total_str}")

        if eta is not None and eta > 0:
            eta_str = self.smart_eta(eta, uploaded)
            lines.append(f"{Box.MIDDLE_LEFT}{Emoji.ETA} <b>ETA:</b> {eta_str}")

        elapsed_str = TimeFormatter.format_seconds(elapsed)
        lines.append(
            f"{Box.BOTTOM_LEFT}{Emoji.TIME} <b>Elapsed:</b> {elapsed_str}")

        message = "\n".join(lines)
        keyboard = ProgressKeyboards.uploading(self.task_id)
        return message, keyboard

    # ------------------------------------------------------------------
    # Compact style
    # ------------------------------------------------------------------

    def _compact_status(
        self,
        operation: str,
        filename: str,
        progress: float,
        speed: float,
        done: int,
        total: int,
        eta: float,
        engine: str
    ) -> "tuple[str, Any]":
        """Compact style - saves vertical space."""
        elapsed = (datetime.now() - self.start_time).total_seconds()

        bar = ProgressBar.generate(progress, 12, "gradient")
        speed_dot = self.speed_emoji(speed)
        speed_str = SizeFormatter.format_speed(speed) if speed > 0 else "--"
        eta_str = self.smart_eta(eta, done)
        elapsed_str = TimeFormatter.format_seconds(elapsed)
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

        keyboard = ProgressKeyboards.downloading(self.task_id)
        return message, keyboard

    # ------------------------------------------------------------------
    # Classic style  (HTML/Markdown mix FIXED)
    # ------------------------------------------------------------------

    def _classic_status(
        self,
        header: str,
        filename: str,
        progress: float,
        speed: float,
        done: int,
        total: int,
        eta: float,
        engine: str
    ) -> "tuple[str, Any]":
        """Classic style - all formatting in HTML (no broken __markdown__ mix)."""
        elapsed = (datetime.now() - self.start_time).total_seconds()

        bar = ProgressBar.generate(progress, 12, "gradient")
        message = f"<b>{header}</b>\n\n"
        message += f"<b>\U0001f3f7\ufe0f Name >> </b><code>{filename}</code>\n\n"
        # FIX: was  __{progress:.1f}%__  (Markdown in HTML mode) - now proper <i> tag
        message += f"\u256d[{bar}] <b>>></b> <i>{progress:.1f}%</i>\n"

        if speed > 0:
            speed_dot = self.speed_emoji(speed)
            message += (
                f"\u251c{speed_dot} <b>Speed >></b> "
                f"<b>{SizeFormatter.format_speed(speed)}</b>\n"
            )

        if engine:
            message += f"\u251c{Emoji.PROCESS} <b>Engine >></b> <b>{engine}</b>\n"

        if eta:
            message += (
                f"\u251c{Emoji.ETA} <b>ETA >></b> "
                f"<i>{self.smart_eta(eta, done)}</i>\n"
            )

        message += (
            f"\u251c{Emoji.TIME} <b>Elapsed >></b> "
            f"<i>{TimeFormatter.format_seconds(elapsed)}</i>\n"
        )
        message += f"\u251c\u2705 <b>Done >></b> <b>{SizeFormatter.format_bytes(done)}</b>\n"
        message += f"\u2570{Emoji.ARCHIVE} <b>Total >></b> <b>{SizeFormatter.format_bytes(total)}</b>"

        keyboard = ProgressKeyboards.downloading(self.task_id)
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
    eta: float = None,
    engine: str = None,
    task_id: str = None,
    style: str = "sleek"
) -> "tuple[str, Any]":
    """Quick download status creation"""
    status = StatusDisplay("Download", task_id)
    return status.download_status(
        filename, progress, speed, downloaded, total_size, eta, engine, style
    )


def create_upload_status(
    filename: str,
    progress: float,
    speed: float,
    uploaded: int,
    total_size: int,
    eta: float = None,
    destination: str = "Telegram",
    task_id: str = None,
    style: str = "sleek"
) -> "tuple[str, Any]":
    """Quick upload status creation"""
    status = StatusDisplay("Upload", task_id)
    return status.upload_status(
        filename, progress, speed, uploaded, total_size, eta, destination, style
    )
