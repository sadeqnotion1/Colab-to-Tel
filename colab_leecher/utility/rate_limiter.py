# /content/Telegram-Leecher/colab_leecher/utility/rate_limiter.py

"""
Rate limiting for task creation to prevent abuse.
"""

import time
import logging
from collections import defaultdict
from typing import Dict, List

log = logging.getLogger(__name__)


class RateLimiter:
    """
    Simple rate limiter for task creation.
    Prevents users from spamming task creation commands.
    """

    def __init__(self, max_requests: int = 10, window_seconds: int = 60):
        """
        Args:
            max_requests: Maximum requests allowed in window
            window_seconds: Time window in seconds
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.user_requests: Dict[int, List[float]] = defaultdict(list)

    def can_proceed(self, user_id: int) -> tuple[bool, str]:
        """
        Check if user can create a new task.

        Returns:
            (allowed, message) - True/False and reason
        """
        now = time.time()

        # Remove old timestamps outside window
        self.user_requests[user_id] = [
            ts for ts in self.user_requests[user_id]
            if now - ts < self.window_seconds
        ]

        # Check if under limit
        request_count = len(self.user_requests[user_id])
        if request_count >= self.max_requests:
            wait_time = int(self.user_requests[user_id][0] + self.window_seconds - now)
            return False, f"⏱️ Rate limit exceeded. You can create {self.max_requests} tasks per minute. Please wait {wait_time}s."

        # Record this request
        self.user_requests[user_id].append(now)
        return True, "OK"

    def cleanup_old_entries(self):
        """Remove entries for users who haven't made requests recently"""
        now = time.time()
        users_to_remove = []

        for user_id, timestamps in self.user_requests.items():
            # Remove timestamps older than window
            recent = [ts for ts in timestamps if now - ts < self.window_seconds]

            if not recent:
                users_to_remove.append(user_id)
            else:
                self.user_requests[user_id] = recent

        for user_id in users_to_remove:
            del self.user_requests[user_id]

        if users_to_remove:
            log.debug(f"Cleaned up rate limiter entries for {len(users_to_remove)} users")


# Global rate limiter instance
RATE_LIMITER = RateLimiter(max_requests=10, window_seconds=60)
