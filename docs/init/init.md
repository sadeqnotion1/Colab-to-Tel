# Batch Parallel Task Handling

This document summarizes how batch downloads, parallel tasks, and Telegram UI updates work. It is intended as a compact reference for contributors.

## Overview

- Multi-task support uses per-task state isolation (`TaskContext`) and a shared queue (`TaskQueue`).
- Concurrent execution is managed with asyncio; per-user and global limits prevent overload.
- Telegram message updates are throttled; parallel mode uses a shared dashboard instead of per-task edits.
- Errors are tracked per task; a single failure does not stop the rest of the batch.

## Key Components

| Area | File | Responsibilities |
| --- | --- | --- |
| Task orchestration | `colab_leecher/utility/task_manager.py` | Creates tasks, loops through links, starts downloads/uploads |
| Download routing | `colab_leecher/downlader/manager.py` | Chooses the correct downloader and handles batch iteration |
| Task isolation | `colab_leecher/utility/task_context.py` | `TaskContext` and `TaskQueue`, limits, locks |
| Status updates | `colab_leecher/utility/helper.py` | `status_bar` throttling and per-task updates |
| Dashboard | `colab_leecher/utility/task_dashboard.py` | Summary message for parallel tasks |
| Cleanup | `colab_leecher/__main__.py` | Task lifecycle and final cleanup |

## Task Flow (High Level)

1. Task created and registered in `TaskQueue`.
2. `downloadManager()` routes each URL to the proper downloader.
3. Progress updates call `status_bar()`:
   - single task: update its own Telegram message
   - multiple tasks: update dashboard summary instead
4. Upload completes and cleanup runs.
5. Task removed from queue; dashboard is refreshed.

## Batch Handling

- `Do_Leech()` currently uses `batch_size = 1`, so URLs are processed sequentially within a task.
- Multiple tasks can still run in parallel across different users or requests.
- Some handlers validate that `batch_filenames` count matches URL count. Keep those aligned to avoid errors.

## Message Update Strategy

Single task:
- Updates its Telegram message directly.
- Minimum interval is 2.5 seconds per task (`status_bar` throttling).

Parallel tasks:
- Per-task message edits are skipped.
- A shared dashboard message is updated at most every 5 seconds.
- Forced updates are debounced to 1 second minimum.
- Summary text is truncated to avoid Telegram size limits.

## Limits and Rate Controls

- `MAX_TASKS_PER_USER = 5`
- `MAX_TOTAL_TASKS = 20`
- `summary_update_interval = 5.0` seconds
- `min_forced_update_interval = 1.0` seconds
- Rate limiter: 10 task creations per 60 seconds per user

Adjust these in `colab_leecher/utility/task_context.py` and `colab_leecher/utility/rate_limiter.py`.

## Error Handling

- Each task has a `TaskError` structure with `state`, `message`, `text`, and `failed_links`.
- Batch handlers append failed items to `failed_links` and continue processing.
- Final reports include success and failure details per task.
- Cancellation sets task status and cancels the asyncio task safely.

## Tuning Notes

- Lowering update intervals below 1 second risks Telegram rate limits.
- Increasing concurrency should be paired with tests for memory, connection pool usage, and dashboard size.
- If you raise `MAX_TOTAL_TASKS`, review dashboard truncation limits first.

## Pointers

- Parallel mode skip logic: `colab_leecher/utility/helper.py`
- Dashboard rendering and truncation: `colab_leecher/utility/task_dashboard.py`
- Task queue enforcement: `colab_leecher/utility/task_context.py`
- Batch download routing: `colab_leecher/downlader/manager.py`
