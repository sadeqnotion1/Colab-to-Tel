# colab_leecher/utility/timeout_manager.py
import asyncio
import logging

log = logging.getLogger(__name__)

class TimeoutManager:
    """
    Tiered timeout system to manage different timeout limits
    for user decisions, file cleanup, and slot releases.
    """
    def __init__(self):
        self._timeouts = {
            'decision': 300,      # 5 minutes for user decision
            'cleanup': 30,        # 30 seconds for cleanup
            'force_release': 10   # 10 seconds for force release
        }
    
    async def wait_with_timeout(self, coro, timeout_type: str):
        timeout = self._timeouts.get(timeout_type, 60.0)
        try:
            return await asyncio.wait_for(coro, timeout=timeout)
        except asyncio.TimeoutError:
            log.warning(f"TimeoutManager: Timeout ({timeout}s) triggered for type '{timeout_type}'")
            raise

_timeout_manager = TimeoutManager()

def get_timeout_manager() -> TimeoutManager:
    return _timeout_manager
