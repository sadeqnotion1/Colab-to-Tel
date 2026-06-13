"""
Enhanced Keyboard Layouts for Telegram Bot
Provides reusable, beautiful inline keyboard configurations
"""

from typing import List, Dict, Union
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup


class KeyboardBuilder:
    """Fluent interface for building keyboards"""

    def __init__(self):
        self.rows: List[List[InlineKeyboardButton]] = []
        self.current_row: List[InlineKeyboardButton] = []

    def button(self, text: str, callback_data: str = None, url: str = None,
               emoji: str = None) -> 'KeyboardBuilder':
        """Add a button to the current row"""
        display_text = f"{emoji} {text}" if emoji else text

        if callback_data:
            btn = InlineKeyboardButton(display_text, callback_data=callback_data)
        elif url:
            btn = InlineKeyboardButton(display_text, url=url)
        else:
            raise ValueError("Either callback_data or url must be provided")

        self.current_row.append(btn)
        return self

    def row(self) -> 'KeyboardBuilder':
        """Start a new row"""
        if self.current_row:
            self.rows.append(self.current_row)
            self.current_row = []
        return self

    def add_row(self, *buttons: InlineKeyboardButton) -> 'KeyboardBuilder':
        """Add a complete row of buttons"""
        if self.current_row:
            self.rows.append(self.current_row)
            self.current_row = []
        self.rows.append(list(buttons))
        return self

    def build(self) -> InlineKeyboardMarkup:
        """Build and return the keyboard"""
        if self.current_row:
            self.rows.append(self.current_row)
            self.current_row = []
        return InlineKeyboardMarkup(self.rows)


class CommonKeyboards:
    """Pre-built common keyboard layouts"""

    @staticmethod
    def cancel(task_id: str = None, text: str = "Cancel", emoji: str = "❌") -> InlineKeyboardMarkup:
        """Single cancel button"""
        from .ui_components_unified import UIComponents
        callback_data = f"cancel:{task_id}" if task_id else "cancel"
        return InlineKeyboardMarkup([
            [UIComponents.cancel_button(callback_data)]
        ])

    @staticmethod
    def confirm_cancel(
        confirm_text: str = "Confirm",
        confirm_data: str = "confirm",
        cancel_text: str = "Cancel",
        cancel_data: str = "cancel"
    ) -> InlineKeyboardMarkup:
        """Confirm and cancel buttons side by side"""
        from .ui_components_unified import UIComponents
        return InlineKeyboardMarkup([
            [
                UIComponents.confirm_button(confirm_data),
                UIComponents.cancel_button(cancel_data)
            ]
        ])

    @staticmethod
    def yes_no(
        yes_data: str = "yes",
        no_data: str = "no",
        yes_text: str = "Yes",
        no_text: str = "No"
    ) -> InlineKeyboardMarkup:
        """Yes/No buttons"""
        from .ui_components_unified import UIComponents
        return InlineKeyboardMarkup([
            [
                UIComponents.confirm_button(yes_data),
                UIComponents.cancel_button(no_data)
            ]
        ])

    @staticmethod
    def back_close(
        back_data: str = "back",
        close_data: str = "close"
    ) -> InlineKeyboardMarkup:
        """Back and Close buttons"""
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton("\u25c0\ufe0f Back", callback_data=back_data),
                InlineKeyboardButton("\u2716 Close", callback_data=close_data)
            ]
        ])

    @staticmethod
    def pagination(
        current_page: int,
        total_pages: int,
        callback_prefix: str = "page"
    ) -> InlineKeyboardMarkup:
        """Pagination buttons"""
        buttons = []

        if current_page > 1:
            buttons.append(InlineKeyboardButton(
                "\u00ab Prev",
                callback_data=f"{callback_prefix}:{current_page - 1}"
            ))

        buttons.append(InlineKeyboardButton(
            f"\u00b7 {current_page}/{total_pages} \u00b7",
            callback_data="page_info"
        ))

        if current_page < total_pages:
            buttons.append(InlineKeyboardButton(
                "Next \u00bb",
                callback_data=f"{callback_prefix}:{current_page + 1}"
            ))

        return InlineKeyboardMarkup([buttons])

    @staticmethod
    def numbered_options(
        options: List[tuple],
        callback_prefix: str = "option",
        columns: int = 1
    ) -> InlineKeyboardMarkup:
        """
        Create numbered option buttons.

        Args:
            options: List of (text, data) tuples
            callback_prefix: Prefix for callback data
            columns: Number of columns (1-3)
        """
        buttons = []
        row = []

        for i, (text, data) in enumerate(options, 1):
            btn = InlineKeyboardButton(
                f"{i}. {text}",
                callback_data=f"{callback_prefix}:{data}"
            )
            row.append(btn)

            if len(row) == columns:
                buttons.append(row)
                row = []

        if row:
            buttons.append(row)

        return InlineKeyboardMarkup(buttons)

    @staticmethod
    def grid(
        items: List[tuple],
        columns: int = 2,
        callback_prefix: str = None
    ) -> InlineKeyboardMarkup:
        """
        Create a grid of buttons.

        Args:
            items: List of (text, callback_data/url) or (text, data, is_url) tuples
            columns: Number of columns
            callback_prefix: Optional prefix for callback data
        """
        buttons = []
        row = []

        for item in items:
            if len(item) == 2:
                text, data = item
                is_url = data.startswith("http")
            else:
                text, data, is_url = item

            if callback_prefix and not is_url:
                data = f"{callback_prefix}:{data}"

            btn = InlineKeyboardButton(text, url=data if is_url else None,
                                       callback_data=None if is_url else data)
            row.append(btn)

            if len(row) == columns:
                buttons.append(row)
                row = []

        if row:
            buttons.append(row)

        return InlineKeyboardMarkup(buttons)

    @staticmethod
    def social_links(
        github: str = None,
        channel: str = None,
        group: str = None,
        website: str = None,
        custom: List[tuple] = None
    ) -> InlineKeyboardMarkup:
        """
        Create social/community links keyboard.

        Args:
            github: GitHub repository URL
            channel: Telegram channel username (with or without @)
            group: Telegram group username
            website: Website URL
            custom: List of (text, url) tuples for custom links
        """
        rows = []

        if github:
            rows.append([InlineKeyboardButton("\u2b50 GitHub", url=github)])

        if channel or group:
            row = []
            if channel:
                channel_url = channel if channel.startswith("http") else f"https://t.me/{channel.lstrip('@')}"
                row.append(InlineKeyboardButton("\U0001f4e3 Channel", url=channel_url))
            if group:
                group_url = group if group.startswith("http") else f"https://t.me/{group.lstrip('@')}"
                row.append(InlineKeyboardButton("\U0001f4ac Group", url=group_url))
            rows.append(row)

        if website:
            rows.append([InlineKeyboardButton("\U0001f310 Website", url=website)])

        if custom:
            for text, url in custom:
                rows.append([InlineKeyboardButton(text, url=url)])

        return InlineKeyboardMarkup(rows)


class MenuKeyboards:
    """Specialized keyboards for menus"""

    @staticmethod
    def main_menu(options: Dict[str, str], close: bool = True) -> InlineKeyboardMarkup:
        """
        Create a main menu keyboard.

        Args:
            options: Dict of {display_text: callback_data}
            close: Add close button at bottom
        """
        kb = KeyboardBuilder()

        for text, data in options.items():
            kb.button(text, callback_data=data).row()

        if close:
            kb.button("\u2716 Close", callback_data="close")

        return kb.build()

    @staticmethod
    def settings_menu(settings: Dict[str, tuple], navigation: bool = True) -> InlineKeyboardMarkup:
        """
        Create a settings menu.

        Args:
            settings: Dict of {label: (current_value, callback_data)}
            navigation: Add back/close buttons
        """
        kb = KeyboardBuilder()

        for label, (value, callback) in settings.items():
            kb.button(f"{label}: {value}", callback_data=callback).row()

        if navigation:
            kb.button("\u25c0\ufe0f Back", callback_data="settings_back")
            kb.button("\u2716 Close", callback_data="close")

        return kb.build()

    @staticmethod
    def selection_menu(
        title_options: List[tuple],
        selected: str = None,
        callback_prefix: str = "select",
        columns: int = 1,
        show_checkmark: bool = True
    ) -> InlineKeyboardMarkup:
        """
        Create a selection menu with checkmarks.

        Args:
            title_options: List of (title, callback_data) tuples
            selected: Currently selected item's callback_data
            callback_prefix: Prefix for callback data
            columns: Number of columns
            show_checkmark: Show checkmark for selected item
        """
        kb = KeyboardBuilder()
        row_count = 0

        for title, data in title_options:
            full_data = f"{callback_prefix}:{data}"
            is_selected = (data == selected)

            if show_checkmark and is_selected:
                text = f"\u2713 {title}"
            else:
                text = title

            kb.button(text, callback_data=full_data)
            row_count += 1

            if row_count >= columns:
                kb.row()
                row_count = 0

        return kb.build()

    @staticmethod
    def toggle_options(
        options: Dict[str, tuple],
        callback_prefix: str = "toggle"
    ) -> InlineKeyboardMarkup:
        """
        Create toggle switches.

        FIX: replaced cramped "Label [\U0001f7e2 ON]" style with clean
        prefix checkmark/square style consistent with selection_menu().

        Args:
            options: Dict of {label: (is_enabled, callback_data)}
            callback_prefix: Prefix for callback data
        """
        kb = KeyboardBuilder()

        for label, (is_enabled, callback) in options.items():
            # \u2705 = green check box  |  \u25fb = white medium square
            icon = "\u2705" if is_enabled else "\u25fb"
            full_callback = f"{callback_prefix}:{callback}"
            kb.button(f"{icon} {label}", callback_data=full_callback).row()

        return kb.build()


class ProgressKeyboards:
    """Keyboards for progress/status messages"""

    @staticmethod
    def downloading(task_id: str = None, show_pause: bool = False) -> InlineKeyboardMarkup:
        """
        Download progress keyboard.

        FIX: contextual label ("Cancel Download" instead of bare "Cancel").
        The show_pause flag is now properly wired up.
        """
        callback_data = f"cancel:{task_id}" if task_id else "cancel"

        if show_pause:
            pause_data = f"pause:{task_id}" if task_id else "pause"
            return InlineKeyboardMarkup([[
                InlineKeyboardButton("\u23f8\ufe0f Pause", callback_data=pause_data),
                InlineKeyboardButton("\u274c Cancel Download", callback_data=callback_data)
            ]])

        return InlineKeyboardMarkup([[
            InlineKeyboardButton("\u274c Cancel Download", callback_data=callback_data)
        ]])

    @staticmethod
    def uploading(task_id: str = None) -> InlineKeyboardMarkup:
        """
        Upload progress keyboard.

        FIX: contextual label ("Cancel Upload" instead of "Stop Upload").
        """
        callback_data = f"cancel:{task_id}" if task_id else "cancel"
        return InlineKeyboardMarkup([[
            InlineKeyboardButton("\U0001f4e4 Cancel Upload", callback_data=callback_data)
        ]])

    @staticmethod
    def processing(task_id: str = None, operation: str = "Processing") -> InlineKeyboardMarkup:
        """
        Processing/extracting keyboard.

        FIX: contextual label with gear emoji instead of bare X.
        """
        callback_data = f"cancel:{task_id}" if task_id else "cancel"
        return InlineKeyboardMarkup([[
            InlineKeyboardButton(f"\u2699\ufe0f Cancel {operation}", callback_data=callback_data)
        ]])


class UtilityKeyboards:
    """Utility keyboard functions"""

    @staticmethod
    def combine(*keyboards: InlineKeyboardMarkup) -> InlineKeyboardMarkup:
        """Combine multiple keyboards"""
        all_rows = []
        for kb in keyboards:
            all_rows.extend(kb.inline_keyboard)
        return InlineKeyboardMarkup(all_rows)

    @staticmethod
    def add_footer(
        keyboard: InlineKeyboardMarkup,
        footer_buttons: List[InlineKeyboardButton]
    ) -> InlineKeyboardMarkup:
        """Add footer row(s) to existing keyboard"""
        rows = list(keyboard.inline_keyboard)
        rows.append(footer_buttons)
        return InlineKeyboardMarkup(rows)

    @staticmethod
    def from_dict(
        layout: Dict[str, Union[str, List[str]]],
        callback_prefix: str = ""
    ) -> InlineKeyboardMarkup:
        """
        Create keyboard from dict structure.

        Args:
            layout: Dict where each key is a row label, value is button text or list
            callback_prefix: Prefix for callback data

        Example:
            {
                "row1": "Single Button",
                "row2": ["Button 1", "Button 2"],
            }
        """
        kb = KeyboardBuilder()

        for row_key, buttons in layout.items():
            if isinstance(buttons, str):
                buttons = [buttons]

            for btn_text in buttons:
                callback = f"{callback_prefix}:{btn_text.lower().replace(' ', '_')}"
                kb.button(btn_text, callback_data=callback)

            kb.row()

        return kb.build()


# Convenience functions for quick keyboard creation
def quick_cancel(task_id: str = None) -> InlineKeyboardMarkup:
    """Quick cancel button"""
    return CommonKeyboards.cancel(task_id)


def quick_confirm(confirm_data: str, cancel_data: str = "cancel") -> InlineKeyboardMarkup:
    """Quick confirm/cancel buttons"""
    return CommonKeyboards.confirm_cancel(
        confirm_data=confirm_data,
        cancel_data=cancel_data
    )


def quick_menu(options: List[tuple], close: bool = True) -> InlineKeyboardMarkup:
    """
    Quick menu creation.

    Args:
        options: List of (text, callback_data) tuples
        close: Add close button
    """
    kb = KeyboardBuilder()

    for text, callback in options:
        kb.button(text, callback_data=callback).row()

    if close:
        kb.button("\u2716 Close", callback_data="close")

    return kb.build()
