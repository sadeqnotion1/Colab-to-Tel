import asyncio
from typing import Any


password_reply_prompts: dict[int, dict[str, Any]] = {}
password_reply_lock = asyncio.Lock()


def _copy_retry_context(retry_context: dict[str, Any] | None) -> dict[str, Any]:
    """Return a shallow copy of retry context while preserving task context reference."""
    if not retry_context:
        return {}
    copied = dict(retry_context)
    if "task_ctx" in retry_context:
        copied["task_ctx"] = retry_context.get("task_ctx")
    return copied


async def set_password_reply_waiting(
    user_id: int,
    chat_id: int,
    prompt_message_id: int,
    retry_context: dict[str, Any] | None,
) -> None:
    """Store per-user password prompt state and retry context."""
    async with password_reply_lock:
        password_reply_prompts[user_id] = {
            "chat_id": chat_id,
            "prompt_message_id": prompt_message_id,
            "retry_context": _copy_retry_context(retry_context),
        }


async def get_password_reply_waiting(user_id: int) -> dict[str, Any] | None:
    """Get per-user password prompt state."""
    async with password_reply_lock:
        state = password_reply_prompts.get(user_id)
        if not state:
            return None
        return {
            "chat_id": state.get("chat_id"),
            "prompt_message_id": state.get("prompt_message_id"),
            "retry_context": _copy_retry_context(state.get("retry_context")),
        }


async def is_password_reply_waiting(user_id: int) -> bool:
    """Check whether user is currently expected to reply with a password."""
    async with password_reply_lock:
        return user_id in password_reply_prompts


async def clear_password_reply_waiting(user_id: int) -> dict[str, Any] | None:
    """Clear per-user password prompt state and return removed state if present."""
    async with password_reply_lock:
        state = password_reply_prompts.pop(user_id, None)

    if not state:
        return None
    return {
        "chat_id": state.get("chat_id"),
        "prompt_message_id": state.get("prompt_message_id"),
        "retry_context": _copy_retry_context(state.get("retry_context")),
    }
