"""
Headless task submission for Colab-to-Tel.

Bypasses the interactive Telegram UI (/tupload -> buttons -> links) and submits
work straight to the SAME engine the UI uses:

    create_task_context() -> _prepare_task_context() -> taskScheduler()

Nothing is forked or duplicated: admission checks (TASK_QUEUE.can_start_task),
per-user locks, worker-slot limits and the strict TaskContext isolation are the
exact production code paths from utility/task_context.py and
utility/task_manager.py.
"""
from __future__ import annotations

import asyncio
import logging
from typing import List, Optional

from ..utility.task_context import TASK_QUEUE, TaskContext, create_task_context
from ..utility.task_manager import taskScheduler

log = logging.getLogger(__name__)


class TaskAdmissionError(RuntimeError):
    """Raised when TASK_QUEUE refuses a new task (limits reached / paused)."""


def _prepare(
    task_ctx: TaskContext,
    links: List[str],
    custom_name: str,
    zip_pswd: str,
    unzip_pswd: str,
    archive_format: str,
) -> None:
    """Reuse the exact context preparation the interactive UI uses.

    The import is deferred on purpose: by the time submit_task() runs, the
    launcher (run_with_controller.py) has already imported
    colab_leecher.__main__ once, so this resolves to the cached module and
    never re-registers handlers.
    """
    from colab_leecher.__main__ import _prepare_task_context

    _prepare_task_context(
        task_ctx,
        source_links=links,
        filenames=[],
        custom_name=custom_name,
        zip_pswd=zip_pswd,
        unzip_pswd=unzip_pswd,
        archive_format=archive_format,
    )


async def _run_task(task_ctx: TaskContext) -> None:
    """Minimal headless runner mirroring run_parallel_task()'s lifecycle:
    register -> acquire worker slot -> taskScheduler -> release slot.
    Completed tasks are left in the queue for the existing periodic cleanup
    (clear_completed_tasks), same as the UI flow.
    """
    task_ctx.mark_started()
    await TASK_QUEUE.add_task(task_ctx)
    await TASK_QUEUE.acquire_worker_slot(task_ctx.task_id)
    try:
        await taskScheduler(task_ctx)
    except asyncio.CancelledError:
        log.warning("Headless task %s cancelled.", task_ctx.get_short_id())
        raise
    except Exception as exc:  # taskScheduler already has its own safety net
        log.exception("Headless task %s failed: %s", task_ctx.get_short_id(), exc)
        if not task_ctx.error.state:
            task_ctx.error.set_error(str(exc))
    finally:
        await TASK_QUEUE.release_worker_slot(task_ctx.task_id)
        if not task_ctx.is_cancelled and not task_ctx.is_completed:
            task_ctx.mark_completed()


async def submit_task(
    links: List[str],
    *,
    mode: str = "leech",
    mode_type: str = "normal",
    service_type: Optional[str] = None,
    custom_name: str = "",
    zip_pswd: str = "",
    unzip_pswd: str = "",
    archive_format: str = "7z",
    user_id: Optional[int] = None,
    chat_id: Optional[int] = None,
) -> TaskContext:
    """Submit a download/upload task programmatically.

    Args mirror the interactive flow: mode in {leech, mirror, gdrive};
    mode_type in {normal, zip, unzip, undzip}; service_type None = auto-detect
    from the links (magnets/direct links are detected downstream, exactly as
    with the UI).

    Returns the created TaskContext (task already running in the background).
    Raises TaskAdmissionError when the queue refuses the task.
    """
    from colab_leecher import OWNER

    if not links:
        raise ValueError("submit_task: 'links' must contain at least one link")

    uid = user_id if user_id is not None else OWNER
    cid = chat_id if chat_id is not None else OWNER

    # Same per-user lock + admission gate as task_starter() in task_manager.py
    user_lock = TASK_QUEUE.get_user_lock(uid)
    async with user_lock:
        can_start, why = await TASK_QUEUE.can_start_task(uid)
        if not can_start:
            raise TaskAdmissionError(why)
        task_ctx = create_task_context(user_id=uid, chat_id=cid, mode=mode)

    task_ctx.mode_type = mode_type
    task_ctx.service_type = service_type
    _prepare(task_ctx, list(links), custom_name, zip_pswd, unzip_pswd, archive_format)

    async_task = asyncio.create_task(
        _run_task(task_ctx), name=f"headless-{task_ctx.get_short_id()}"
    )
    task_ctx.async_task = async_task
    log.info(
        "Headless task %s submitted (%d link(s), mode=%s/%s)",
        task_ctx.get_short_id(), len(links), mode, mode_type,
    )
    return task_ctx
