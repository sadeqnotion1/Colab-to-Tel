"""
Enhanced Telegram Bot UI Components
Provides modern, beautiful message templates and formatting utilities
"""

from typing import List, Dict, Any


class Emoji:
    """Emoji constants for consistent usage"""
    # Status
    SUCCESS = "\u2705"
    ERROR = "\u274c"
    WARNING = "\u26a0\ufe0f"
    INFO = "\u2139\ufe0f"
    LOADING = "\u23f3"

    # Actions
    DOWNLOAD = "\U0001f4e5"
    UPLOAD = "\U0001f4e4"
    PROCESS = "\u2699\ufe0f"
    EXTRACT = "\U0001f4c2"
    COMPRESS = "\U0001f5dc\ufe0f"

    # File types
    VIDEO = "\U0001f3a5"
    AUDIO = "\U0001f3b5"
    DOCUMENT = "\U0001f4c4"
    PHOTO = "\U0001f5bc\ufe0f"
    ARCHIVE = "\U0001f4e6"
    FOLDER = "\U0001f4c1"
    FILE = "\U0001f4c4"   # alias for DOCUMENT — fixes AttributeError in success_message()

    # Progress
    SPEED = "\u26a1"
    TIME = "\u23f1\ufe0f"
    ETA = "\u23f3"
    SIZE = "\U0001f4be"

    # UI
    ARROW_RIGHT = "\u25b6\ufe0f"
    ARROW_LEFT = "\u25c0\ufe0f"
    BULLET = "\u2022"
    DASH = "\u2014"
    CHECK = "\u2713"
    CROSS = "\u2717"

    # Misc
    FIRE = "\U0001f525"
    ROCKET = "\U0001f680"
    STAR = "\u2b50"
    SPARKLE = "\u2728"
    LINK = "\U0001f517"
    TAG = "\U0001f3f7\ufe0f"
    BRAIN = "\U0001f9e0"


class Box:
    """Box drawing characters for beautiful layouts"""
    # Single line
    TOP_LEFT = "\u256d"
    TOP_RIGHT = "\u256e"
    BOTTOM_LEFT = "\u2570"
    BOTTOM_RIGHT = "\u256f"
    HORIZONTAL = "\u2500"
    VERTICAL = "\u2502"
    MIDDLE_LEFT = "\u251c"
    MIDDLE_RIGHT = "\u2524"

    # Double line
    D_TOP_LEFT = "\u2554"
    D_TOP_RIGHT = "\u2557"
    D_BOTTOM_LEFT = "\u255a"
    D_BOTTOM_RIGHT = "\u255d"
    D_HORIZONTAL = "\u2550"
    D_VERTICAL = "\u2551"

    # Heavy
    H_HORIZONTAL = "\u2501"
    H_VERTICAL = "\u2503"


class ProgressBar:
    """Enhanced progress bar generator"""

    @staticmethod
    def generate(percentage: float, length: int = 12, style: str = "blocks") -> str:
        """
        Generate a progress bar.

        Args:
            percentage: Completion percentage (0-100)
            length: Bar length in characters
            style: 'blocks', 'circles', 'squares', 'dots', 'arrows', 'gradient'

        Returns:
            Formatted progress bar string (no surrounding brackets)
        """
        percentage = max(0, min(100, percentage))
        filled = int((percentage / 100) * length)

        styles = {
            'blocks': ('\u2588', '\u2591'),
            'circles': ('\u25cf', '\u25cb'),
            'squares': ('\u25a0', '\u25a1'),
            'dots': ('\u2b24', '\u25ef'),
            'arrows': ('\u25b0', '\u25b1'),
            'gradient': ('\u2588', '\u2593', '\u2592', '\u2591'),
        }

        if style == 'gradient' and length >= 4:
            chars = styles['gradient']
            full_blocks = filled
            partial = int(((percentage / 100) * length - filled) * (len(chars) - 1))

            bar = chars[0] * full_blocks
            if partial > 0 and filled < length:
                bar += chars[partial]
                bar += chars[-1] * (length - filled - 1)
            else:
                bar += chars[-1] * (length - filled)
            return bar

        filled_char, empty_char = styles.get(style, styles['blocks'])
        return filled_char * filled + empty_char * (length - filled)

    @staticmethod
    def with_percentage(percentage: float, length: int = 12, style: str = "blocks") -> str:
        """Generate progress bar with percentage"""
        bar = ProgressBar.generate(percentage, length, style)
        return f"[{bar}] {percentage:.1f}%"

    @staticmethod
    def custom(percentage: float, prefix: str = "", suffix: str = "",
               length: int = 12, style: str = "blocks") -> str:
        """Generate custom progress bar with prefix/suffix"""
        bar = ProgressBar.generate(percentage, length, style)
        return f"{prefix}[{bar}]{suffix}".strip()


class MessageTemplate:
    """Pre-built message templates for common scenarios"""

    @staticmethod
    def header(title: str, emoji: str = "") -> str:
        """Create a bold header"""
        return f"<b>{emoji} {title}</b>\n" if emoji else f"<b>{title}</b>\n"

    @staticmethod
    def field(label: str, value: str, emoji: str = "", use_code: bool = False) -> str:
        """Create a labeled field"""
        emoji_str = f"{emoji} " if emoji else ""
        value_formatted = f"<code>{value}</code>" if use_code else value
        return f"{emoji_str}<b>{label}:</b> {value_formatted}"

    @staticmethod
    def divider(char: str = "\u2500", length: int = 25) -> str:
        """Create a divider line"""
        return char * length

    @staticmethod
    def box_list(items: List[tuple], title: str = None) -> str:
        """
        Create a boxed list.

        Args:
            items: List of (emoji, label, value) or (emoji, value) tuples
            title: Optional title for the box
        """
        lines = []

        if title:
            lines.append(f"<b>{title}</b>")

        for i, item in enumerate(items):
            if len(item) == 2:
                emoji, value = item
                label = ""
            else:
                emoji, label, value = item

            is_first = (i == 0)
            is_last = (i == len(items) - 1)

            if is_first and is_last:
                prefix = Box.BOTTOM_LEFT
            elif is_first:
                prefix = Box.TOP_LEFT
            elif is_last:
                prefix = Box.BOTTOM_LEFT
            else:
                prefix = Box.MIDDLE_LEFT

            label_str = f"<b>{label}:</b> " if label else ""
            lines.append(f"{prefix}{emoji} {label_str}{value}")

        return "\n".join(lines)

    @staticmethod
    def card(title: str, items: Dict[str, Any], emoji_map: Dict[str, str] = None) -> str:
        """
        Create a card-style message.

        Args:
            title: Card title
            items: Dict of label: value pairs
            emoji_map: Optional dict mapping labels to emojis
        """
        emoji_map = emoji_map or {}
        lines = [f"<b>{Emoji.SPARKLE} {title}</b>\n"]

        item_list = list(items.items())
        for i, (label, value) in enumerate(item_list):
            emoji = emoji_map.get(label, Emoji.BULLET)
            is_first = (i == 0)
            is_last = (i == len(item_list) - 1)

            if is_first and is_last:
                prefix = Box.BOTTOM_LEFT
            elif is_first:
                prefix = Box.TOP_LEFT
            elif is_last:
                prefix = Box.BOTTOM_LEFT
            else:
                prefix = Box.MIDDLE_LEFT

            lines.append(f"{prefix}{emoji} <b>{label}:</b> {value}")

        return "\n".join(lines)

    @staticmethod
    def status_message(
        title: str,
        status: str,
        progress: float = None,
        details: Dict[str, str] = None,
        show_progress_bar: bool = True
    ) -> str:
        """
        Create a comprehensive status message.

        Args:
            title: Main title
            status: Current status text
            progress: Progress percentage (0-100)
            details: Additional details dict
            show_progress_bar: Whether to show progress bar
        """
        lines = [f"<b>{Emoji.ROCKET} {title}</b>\n"]

        # Build field list
        fields = [f"{Emoji.INFO} <b>Status:</b> <i>{status}</i>"]

        if progress is not None and show_progress_bar:
            bar = ProgressBar.generate(progress, 12, 'gradient')
            fields.append(f"[{bar}] <b>{progress:.1f}%</b>")

        if details:
            for key, value in details.items():
                fields.append(f"{Emoji.BULLET} <b>{key}:</b> {value}")

        for i, content in enumerate(fields):
            is_first = (i == 0)
            is_last = (i == len(fields) - 1)
            if is_first and is_last:
                prefix = Box.BOTTOM_LEFT
            elif is_first:
                prefix = Box.TOP_LEFT
            elif is_last:
                prefix = Box.BOTTOM_LEFT
            else:
                prefix = Box.MIDDLE_LEFT
            lines.append(f"{prefix}{content}")

        return "\n".join(lines)

    @staticmethod
    def error_message(
        title: str,
        error: str,
        details: str = None,
        solution: str = None
    ) -> str:
        """Create a formatted error message.

        FIX: replaced brittle lines[-1].replace(MIDDLE_LEFT, BOTTOM_LEFT)
        with index-aware prefix assignment.
        """
        lines = [f"<b>{Emoji.ERROR} {title}</b>\n"]

        # Collect all field contents first so we know count
        fields = [f"{Emoji.WARNING} <b>Error:</b> <code>{error}</code>"]
        if details:
            fields.append(f"{Emoji.INFO} <b>Details:</b> {details}")
        if solution:
            fields.append(f"{Emoji.BRAIN} <b>Solution:</b> <i>{solution}</i>")

        for i, content in enumerate(fields):
            is_first = (i == 0)
            is_last = (i == len(fields) - 1)
            if is_first and is_last:
                prefix = Box.BOTTOM_LEFT
            elif is_first:
                prefix = Box.TOP_LEFT
            elif is_last:
                prefix = Box.BOTTOM_LEFT
            else:
                prefix = Box.MIDDLE_LEFT
            lines.append(f"{prefix}{content}")

        return "\n".join(lines)

    @staticmethod
    def success_message(
        title: str,
        summary: Dict[str, str],
        files: List[str] = None,
        show_hashtag: bool = True
    ) -> str:
        """Create a success/completion message.

        FIX: replaced Emoji.FILE (undefined) with Emoji.DOCUMENT.
        """
        lines = []

        if show_hashtag:
            hashtag = title.upper().replace(" ", "_")
            lines.append(f"#{hashtag} {Emoji.FIRE}\n")

        lines.append(f"<b>{Emoji.SUCCESS} {title}</b>\n")

        # Build all row content first for correct prefix assignment
        rows = []
        for key, value in summary.items():
            rows.append(f"{Emoji.BULLET} <b>{key}:</b> {value}")
        if files:
            rows.append(f"{Emoji.DOCUMENT} <b>Files:</b>")   # was Emoji.FILE

        for i, content in enumerate(rows):
            is_first = (i == 0)
            is_last = (i == len(rows) - 1) and not files
            if is_first and is_last:
                prefix = Box.BOTTOM_LEFT
            elif is_first:
                prefix = Box.TOP_LEFT
            elif is_last:
                prefix = Box.BOTTOM_LEFT
            else:
                prefix = Box.MIDDLE_LEFT
            lines.append(f"{prefix}{content}")

        if files:
            for i, file in enumerate(files):
                is_last = (i == len(files) - 1)
                prefix = Box.BOTTOM_LEFT if is_last else Box.MIDDLE_LEFT
                lines.append(f"{prefix}  {Emoji.ARROW_RIGHT} <code>{file}</code>")

        return "\n".join(lines)

    @staticmethod
    def menu_header(title: str, description: str = None, emoji: str = None) -> str:
        """Create a menu header"""
        emoji = emoji or Emoji.ROCKET
        lines = [f"<b>{emoji} {title}</b>"]

        if description:
            lines.append(f"\n<i>{description}</i>")

        lines.append("")  # Empty line
        return "\n".join(lines)

    @staticmethod
    def option_list(options: List[tuple], numbered: bool = True) -> str:
        """
        Create a numbered/bulleted option list.

        Args:
            options: List of (title, description) tuples
            numbered: Use numbers instead of bullets
        """
        lines = []

        for i, (title, description) in enumerate(options, 1):
            prefix = f"<b>{i}.</b>" if numbered else Emoji.BULLET
            lines.append(f"{prefix} <b>{title}</b>")
            if description:
                lines.append(f"   <i>{description}</i>")
            lines.append("")  # Empty line between options

        return "\n".join(lines)


class TimeFormatter:
    """Format time durations"""

    @staticmethod
    def format_seconds(seconds: float) -> str:
        """Format seconds into human readable format"""
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            minutes = int(seconds // 60)
            secs = int(seconds % 60)
            return f"{minutes}m {secs}s"
        else:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            return f"{hours}h {minutes}m"

    @staticmethod
    def format_eta(seconds: float) -> str:
        """Format ETA with special handling"""
        if seconds < 0 or seconds > 86400 * 7:  # More than a week
            return "Calculating..."
        return TimeFormatter.format_seconds(seconds)


class SizeFormatter:
    """Format file sizes"""

    @staticmethod
    def format_bytes(bytes_size: int, precision: int = 2) -> str:
        """Format bytes into human readable size"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_size < 1024.0:
                return f"{bytes_size:.{precision}f} {unit}"
            bytes_size /= 1024.0
        return f"{bytes_size:.{precision}f} PB"

    @staticmethod
    def format_speed(bytes_per_second: float) -> str:
        """Format speed (bytes/second)"""
        return f"{SizeFormatter.format_bytes(bytes_per_second)}/s"


# Module-level alias (kept for any existing imports)
FILE = Emoji.DOCUMENT
