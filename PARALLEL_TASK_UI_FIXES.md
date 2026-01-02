# Parallel Task UI Fixes Report

## Identified Problems

1.  **Markdown Truncation Error (CRITICAL)**
    *   **Issue:** The summary dashboard was building a single large string of all tasks and then naively truncating it at 1024 (caption) or 4096 (text) characters.
    *   **Consequence:** This often cut off Markdown entities (like `**Bold**` becoming `**Bol`) or code blocks (` `Code` ` becoming ` `Co`), causing Telegram's parser to reject the message edit with `Bad Request: can't parse entities`.
    *   **Result:** The dashboard would freeze, stop updating, or flicker as the bot tried to recreate the message repeatedly.

2.  **Resource Leak Potential (Minor)**
    *   **Issue:** The `force_update_summary` function created background tasks for delayed updates but didn't explicitly manage their lifecycle, although `asyncio.create_task` handles this reasonably well.
    *   **Result:** Potential for minor inefficiency or race conditions in very high-load scenarios.

## Applied Fixes

### 1. Robust Line-Based Truncation
*   **File:** `colab_leecher/utility/task_dashboard.py`
*   **Fix:** Rewrote `update_summary_dashboard` to check the message length *line by line* as it is built.
*   **Logic:**
    *   Defined strict character limits: 900 for photos (leaving buffer for header/footer), 3800 for text.
    *   If adding a new task line would exceed the limit, the loop stops immediately.
    *   A warning `⚠️ **+ X more tasks...**` is appended.
    *   This ensures that no Markdown entity is ever split in half, preventing parser errors.

### 2. Button Consistency
*   **File:** `colab_leecher/utility/task_dashboard.py`
*   **Fix:** The "Cancel Task X" buttons are now generated only for the tasks *actually shown* in the message to avoid confusion (buttons for hidden truncated tasks).

## Verification
*   **Dashboard Updates:** Should now be smooth even with 20+ active tasks.
*   **Truncation:** If the list is too long, it will gracefully show "+ X more tasks" instead of crashing or freezing.
*   **Status:** "Initializing..." stuck state was addressed in a previous patch (NZBCloud fix), and the dashboard logic correctly reflects `down_bytes > 0` progress.
