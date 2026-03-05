from __future__ import annotations

from pathlib import Path

from tests.unit._module_loader import load_module


REPO_ROOT = Path(__file__).resolve().parents[2]


def _read(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


def test_ui_copy_link_prompt_and_cancel_label_are_consistent() -> None:
    module = load_module("colab_leecher/utility/ui_copy.py", "ui_copy_contract_test")

    prompt = module.build_link_prompt("Leech to Telegram", task_id="abcd1234")
    label = module.build_cancel_task_button_label(
        "very_long_file_name_that_should_be_trimmed.mp4",
        None,
        "abcd1234",
        max_name_length=16,
    )

    assert "Supported sources:" in prompt
    assert "<code>abcd1234</code>" in prompt
    assert label.startswith("Cancel ")
    assert "(abcd1234)" in label


def test_cancel_all_tasks_uses_explicit_confirmation_flow() -> None:
    source = _read("colab_leecher/__main__.py")

    assert 'callback_data="cancel_all_tasks_confirm"' in source
    assert 'callback_data="cancel_all_tasks_abort"' in source
    assert 'query_data == "cancel_all_tasks_confirm"' in source
    assert "Cancel all active tasks (" in source


def test_dashboard_uses_named_cancel_buttons_not_indexed_buttons() -> None:
    source = _read("colab_leecher/utility/task_dashboard.py")

    assert "build_cancel_task_button_label" in source
    assert "Cancel Task {idx}" not in source
    assert "Active Tasks" in source


def test_final_summary_card_no_longer_uses_legacy_complete_hashtag() -> None:
    source = _read("colab_leecher/utility/handler.py")

    assert "_COMPLETE</b>" not in source
    assert "Name »" not in source
    assert "Time Taken »" not in source
