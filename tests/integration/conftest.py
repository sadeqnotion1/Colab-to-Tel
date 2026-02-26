from __future__ import annotations

import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--runintegration",
        action="store_true",
        default=False,
        help="Run integration tests.",
    )


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "integration: mark tests as integration tests requiring --runintegration",
    )


def pytest_collection_modifyitems(config, items):
    if config.getoption("--runintegration"):
        return

    skip_integration = pytest.mark.skip(
        reason="integration tests require --runintegration"
    )
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_integration)
