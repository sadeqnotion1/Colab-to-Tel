from __future__ import annotations

from tests.unit._module_loader import load_module


def test_progress_bar_clamps_percentage_and_preserves_length():
    module = load_module("colab_leecher/utility/ui_components.py", "ui_components_progress_test")
    empty_bar = module.ProgressBar.generate(-50, length=10)
    full_bar = module.ProgressBar.generate(250, length=10)

    assert len(empty_bar) == 10
    assert len(full_bar) == 10
    assert empty_bar != full_bar


def test_progress_bar_with_percentage_format():
    module = load_module("colab_leecher/utility/ui_components.py", "ui_components_percent_test")
    rendered = module.ProgressBar.with_percentage(42.34, length=8)

    assert rendered.startswith("[")
    assert rendered.endswith("%")
    assert "42.3%" in rendered


def test_progress_bar_ascii_style_uses_safe_characters():
    module = load_module("colab_leecher/utility/ui_components.py", "ui_components_ascii_test")
    bar = module.ProgressBar.generate(55, length=10, style="ascii")

    assert len(bar) == 10
    assert set(bar).issubset({"=", "-"})


def test_time_and_size_formatters_are_deterministic():
    module = load_module("colab_leecher/utility/ui_components.py", "ui_components_formatter_test")

    assert module.TimeFormatter.format_seconds(65) == "1m 5s"
    assert module.TimeFormatter.format_eta(3600) == "1h 0m"
    assert module.SizeFormatter.format_bytes(1024) == "1.00 KB"
