from __future__ import annotations

from tests.unit._module_loader import load_module


def test_rate_limiter_allows_requests_within_limit(monkeypatch):
    module = load_module("colab_leecher/utility/rate_limiter.py", "rate_limiter_under_test")
    limiter = module.RateLimiter(max_requests=2, window_seconds=60)
    fake_times = iter([0.0, 1.0])
    monkeypatch.setattr(module.time, "time", lambda: next(fake_times))

    allowed1, msg1 = limiter.can_proceed(user_id=7)
    allowed2, msg2 = limiter.can_proceed(user_id=7)

    assert allowed1 is True
    assert msg1 == "OK"
    assert allowed2 is True
    assert msg2 == "OK"


def test_rate_limiter_blocks_after_limit(monkeypatch):
    module = load_module("colab_leecher/utility/rate_limiter.py", "rate_limiter_block_test")
    limiter = module.RateLimiter(max_requests=2, window_seconds=60)
    fake_times = iter([0.0, 1.0, 2.0])
    monkeypatch.setattr(module.time, "time", lambda: next(fake_times))

    assert limiter.can_proceed(user_id=99)[0] is True
    assert limiter.can_proceed(user_id=99)[0] is True
    allowed, message = limiter.can_proceed(user_id=99)

    assert allowed is False
    assert "Rate limit exceeded" in message


def test_cleanup_old_entries_removes_stale_users(monkeypatch):
    module = load_module("colab_leecher/utility/rate_limiter.py", "rate_limiter_cleanup_test")
    limiter = module.RateLimiter(max_requests=2, window_seconds=10)
    limiter.user_requests[1] = [1.0]
    limiter.user_requests[2] = [19.0]
    monkeypatch.setattr(module.time, "time", lambda: 20.0)

    limiter.cleanup_old_entries()

    assert 1 not in limiter.user_requests
    assert 2 in limiter.user_requests
