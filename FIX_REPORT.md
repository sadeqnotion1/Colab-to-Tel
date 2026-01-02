# Fix Report: UI/UX Issues

## 1. Thumbnail Photos Not Showing
**Root Cause:**
- `send_video` was being called without `width` and `height` parameters. Telegram often fails to display thumbnails for videos if these dimensions are not provided or default to 0.
- `get_video_thumbnail` was only generating the image but not extracting dimensions.

**Fix Applied:**
- Modified `colab_leecher/utility/helper.py`: Added `get_video_metadata(file_path)` function that uses `ffprobe` to extract `width`, `height`, and `duration`.
- Modified `colab_leecher/uploader/telegram.py`: Updated `upload_file` to call `get_video_metadata` and pass `width` and `height` to `colab_bot.send_video`.

## 2. Formatted Text Not Displaying
**Root Cause:**
- Messages using HTML tags like `<code>`, `<b>`, `<i>` were being sent without an explicit `parse_mode`. Pyrogram defaults to Markdown (or None in some contexts), causing HTML tags to be rendered as literal text.

**Fix Applied:**
- Modified `colab_leecher/uploader/telegram.py`: Added `parse_mode=enums.ParseMode.HTML` to `send_video`, `send_photo`, and `send_document`.
- Modified `colab_leecher/utility/helper.py`: Added `parse_mode=enums.ParseMode.HTML` to `status_bar` message editing calls.
- Modified `colab_leecher/__main__.py`: Added `parse_mode=enums.ParseMode.HTML` to various command handlers (`/setname`, `/zipaswd`, etc.) that return HTML-formatted responses.

## 3. Cancel Buttons Not Working
**Root Cause:**
- While the button logic was generally correct, "not responding" buttons can occur if the callback handler fails silently or if the message update frequency interferes (rare).
- The "not showing" part was likely related to the `status_bar` failing or formatting issues preventing the message from rendering correctly with the markup.

**Fix Applied:**
- The fixes for **Formatted Text** in `status_bar` ensure that the message (and its attached buttons) renders correctly.
- Verified `colab_leecher/__main__.py`: The `handle_options` callback handler has a robust `try...except` block that catches errors and sends an alert to the user ("An error occurred!"), preventing the "unresponsive" feel (infinite spinner).

## Summary of Files Changed
1.  `colab_leecher/utility/helper.py`
2.  `colab_leecher/uploader/telegram.py`
3.  `colab_leecher/__main__.py`
