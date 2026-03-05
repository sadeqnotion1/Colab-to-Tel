from __future__ import annotations

import re
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


def test_alias_prompts_use_shared_ui_copy_builders() -> None:
    source = _read("colab_leecher/aliases.py")

    assert "build_link_prompt(" in source
    assert "build_ytdl_prompt(" in source
    assert "build_instagram_prompt(" in source
    assert "build_nzbcloud_prompt(" in source
    assert "Send Me THEM LINK(s)" not in source
    assert "Send Me LINK(s)" not in source


def test_primary_runtime_copy_is_html_only_in_targeted_modules() -> None:
    targeted_files = [
        "colab_leecher/__main__.py",
        "colab_leecher/aliases.py",
        "colab_leecher/utility/task_manager.py",
        "colab_leecher/utility/converters.py",
        "colab_leecher/utility/helper.py",
        "colab_leecher/utility/task_context.py",
    ]

    for relative_path in targeted_files:
        source = _read(relative_path)
        assert re.search(r"\*\*[^*\n]+\*\*", source) is None
        assert re.search(r"`[^`\n]+`", source) is None


def test_primary_runtime_copy_uses_explicit_html_parse_mode() -> None:
    main_source = _read("colab_leecher/__main__.py")
    task_manager_source = _read("colab_leecher/utility/task_manager.py")

    assert "parse_mode=enums.ParseMode.HTML" in main_source
    assert "parse_mode=enums.ParseMode.HTML" in task_manager_source


def test_status_and_health_text_use_shared_ui_copy_templates() -> None:
    converters_source = _read("colab_leecher/utility/converters.py")
    helper_source = _read("colab_leecher/utility/helper.py")
    task_context_source = _read("colab_leecher/utility/task_context.py")

    assert "build_archiver_progress_text(" in converters_source
    assert "build_archiver_verification_text(" in converters_source
    assert "build_converter_progress_text(" in converters_source
    assert "build_settings_text(" in helper_source
    assert "build_health_summary_text(" in task_context_source
