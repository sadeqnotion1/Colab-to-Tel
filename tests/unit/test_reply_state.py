from __future__ import annotations

import asyncio

from colab_leecher.utility.reply_state import (
    clear_password_reply_waiting,
    get_password_reply_waiting,
    is_password_reply_waiting,
    set_password_reply_waiting,
)


def test_password_reply_state_roundtrip() -> None:
    user_id = 987654

    asyncio.run(clear_password_reply_waiting(user_id))

    retry_context = {
        "zip_filepath": "/tmp/archive.zip",
        "remove": True,
    }
    asyncio.run(
        set_password_reply_waiting(
            user_id=user_id,
            chat_id=12345,
            prompt_message_id=4321,
            retry_context=retry_context,
        )
    )

    state = asyncio.run(get_password_reply_waiting(user_id))
    assert state is not None
    assert state["chat_id"] == 12345
    assert state["prompt_message_id"] == 4321
    assert state["retry_context"]["zip_filepath"] == "/tmp/archive.zip"
    assert state["retry_context"]["remove"] is True
    assert asyncio.run(is_password_reply_waiting(user_id)) is True

    # Verify stored context is copied and does not alias caller's dict.
    retry_context["remove"] = False
    state_after_mutation = asyncio.run(get_password_reply_waiting(user_id))
    assert state_after_mutation is not None
    assert state_after_mutation["retry_context"]["remove"] is True

    cleared = asyncio.run(clear_password_reply_waiting(user_id))
    assert cleared is not None
    assert cleared["prompt_message_id"] == 4321
    assert asyncio.run(get_password_reply_waiting(user_id)) is None
    assert asyncio.run(is_password_reply_waiting(user_id)) is False


def test_clear_password_reply_state_missing_user() -> None:
    missing_user_id = 11111111
    result = asyncio.run(clear_password_reply_waiting(missing_user_id))
    assert result is None
