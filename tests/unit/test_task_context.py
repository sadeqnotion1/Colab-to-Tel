# tests/unit/test_task_context.py

import sys
import os
from unittest.mock import MagicMock

# Create a mock module structure to satisfy imports
class MockModule(MagicMock):
    @property
    def __path__(self):
        return []

sys.modules['pyrogram'] = MockModule()
sys.modules['pyrogram.client'] = MockModule()
sys.modules['pyrogram.types'] = MockModule()
sys.modules['pyrogram.enums'] = MockModule()
sys.modules['pyrogram.errors'] = MockModule()

# Add the project root to sys.path so we can import colab_leecher
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from colab_leecher.utility.task_context import create_task_context, TaskContext
from colab_leecher.utility.variables import Paths

def test_create_task_context_success():
    # Attempt to create a task context. This verifies that:
    # 1. Isolation phase works successfully.
    # 2. No IsolationError is raised due to class attributes like '_os' module.
    ctx = create_task_context(user_id=121110934, chat_id=121110934, mode="leech")
    
    assert isinstance(ctx, TaskContext)
    assert ctx.user_id == 121110934
    assert ctx.chat_id == 121110934
    assert ctx.service_type is None
    
    # Verify Paths has been isolated successfully
    assert hasattr(ctx, "paths")
    assert not hasattr(ctx.paths, "_os")
    assert ctx.paths.WORK_PATH.startswith(Paths.WORK_PATH)

if __name__ == "__main__":
    print("Running task context isolation test...")
    test_create_task_context_success()
    print("Test passed successfully!")
