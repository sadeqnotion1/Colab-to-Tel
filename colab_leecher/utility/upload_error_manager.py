# colab_leecher/utility/upload_error_manager.py
import asyncio
import logging
import time
from .timeout_manager import get_timeout_manager

log = logging.getLogger(__name__)

class UploadErrorManager:
    """
    Centralized manager for upload errors.
    Handles releasing/re-acquiring worker slots, waiting for user decisions with timeouts,
    and automatic cleanup of files to prevent leaks.
    """
    def __init__(self):
        self._pending_errors = {}  # task_id -> state dict
        self._lock = asyncio.Lock()

    async def handle_upload_error(self, task_ctx, error):
        """
        Handles upload errors with proper worker slot releasing, user decision waiting with timeout,
        and post-decision cleanup to prevent slot leaks.
        """
        task_id = task_ctx.task_id
        short_id = task_ctx.get_short_id()
        
        async with self._lock:
            self._pending_errors[task_id] = {
                'timestamp': time.monotonic(),
                'task_ctx': task_ctx,
                'error': error
            }

        # 1. Release worker slot immediately during the user wait
        from .task_context import TASK_QUEUE
        log.info(f"UploadErrorManager: Releasing worker slot for task {short_id} during user decision wait")
        await TASK_QUEUE.release_worker_slot(task_id)

        # 2. Change action to AWAITING_UPLOAD_DECISION
        from .transfer_state import AWAITING_UPLOAD_DECISION
        task_ctx.messages.current_action = AWAITING_UPLOAD_DECISION

        # 3. Send Pyrogram message with InlineKeyboardMarkup
        from .ui_components import MessageTemplate
        from .. import colab_bot
        
        keyboard = MessageTemplate.get_upload_error_keyboard(task_ctx)
        
        # Format context-aware error message
        download_name = task_ctx.messages.download_name or "Unknown Download"
        msg_text = (
            f"⚠️ **Upload/Split Failed**\n\n"
            f"📁 **Task**: `{download_name}`\n"
            f"🔍 **Error**: `{str(error)[:150]}`\n\n"
            f"Files are saved locally. What would you like to do?"
        )
        
        try:
            await colab_bot.send_message(
                chat_id=task_ctx.chat_id,
                text=msg_text,
                reply_markup=keyboard
            )
        except Exception as e:
            log.error(f"UploadErrorManager: Failed to send upload error keyboard message: {e}")

        # 4. Wait for decision (with tiered timeout: 5 minutes instead of 1 hour)
        log.info(f"UploadErrorManager: Task {short_id} paused, waiting for user decision...")
        tm = get_timeout_manager()
        
        timeout_occurred = False
        try:
            await tm.wait_with_timeout(task_ctx.user_decision_event.wait(), 'decision')
        except asyncio.TimeoutError:
            log.warning(f"UploadErrorManager: Task {short_id} timed out waiting for user decision.")
            timeout_occurred = True
            task_ctx.keep_files_decision = False

        # 5. Clean up pending errors dict
        async with self._lock:
            self._pending_errors.pop(task_id, None)

        # 6. Re-acquire worker slot before resuming pipeline or propagating the error
        log.info(f"UploadErrorManager: Re-acquiring worker slot for task {short_id}")
        await TASK_QUEUE.acquire_worker_slot(task_id)

        # 7. Process decision
        if timeout_occurred:
            from .task_context import cleanup_task_artifacts
            log.info(f"UploadErrorManager: Timeout occurred. Cleaning up workspace for task {short_id}...")
            cleanup_task_artifacts(task_ctx)
            raise Exception(f"Upload/split timed out waiting for user decision. Original error: {error}")
            
        decision = getattr(task_ctx, "keep_files_decision", False)
        if decision == "cancel":
            log.info(f"UploadErrorManager: User decided to cancel task {short_id}. Cleaning up workspace...")
            from .task_context import cleanup_task_artifacts
            cleanup_task_artifacts(task_ctx)
            task_ctx.is_aborted = True
            raise Exception("Cancelled by user after upload error.")
            
        elif decision is True:
            log.info(f"UploadErrorManager: User decided to keep files for task {short_id}. Marking task as ABORTED.")
            task_ctx.is_aborted = True
            raise Exception("ABORTED")
            
        else:
            log.info(f"UploadErrorManager: User decided to delete files for task {short_id}. Cleaning up workspace...")
            from .task_context import cleanup_task_artifacts
            cleanup_task_artifacts(task_ctx)
            raise Exception(f"Upload/split failed: {error}")

_upload_error_manager = UploadErrorManager()

def get_upload_error_manager() -> UploadErrorManager:
    return _upload_error_manager

async def cleanup_stuck_errors():
    """
    Clean up errors that exceeded timeout (10 minutes).
    Runs periodically as a background task.
    """
    uem = get_upload_error_manager()
    while True:
        try:
            await asyncio.sleep(60)  # Check every minute
            now = time.monotonic()
            stuck_tasks = []
            async with uem._lock:
                for task_id, info in uem._pending_errors.items():
                    if now - info['timestamp'] > 600.0:
                        stuck_tasks.append(info['task_ctx'])
            
            for task_ctx in stuck_tasks:
                log.warning(f"UploadErrorManager: Force cleaning up stuck error for task {task_ctx.get_short_id()}")
                task_ctx.keep_files_decision = False
                task_ctx.user_decision_event.set()
        except asyncio.CancelledError:
            break
        except Exception as e:
            log.error(f"Error in cleanup_stuck_errors loop: {e}", exc_info=True)
