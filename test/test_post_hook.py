import os
import sys
import shutil
import asyncio
import types
import importlib.util
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 1. Create mock utility modules
variables_mock = types.ModuleType("colab_leecher.utility.variables")
class MockSetting:
    instagram_username = ""
    instagram_password = ""
    instagram_sessionid = ""
    instagram_cookies_file = ""
    instagram_session = ""
class MockBOT:
    Setting = MockSetting()
class MockPaths:
    WORK_PATH = str(PROJECT_ROOT / "BOT_WORK")
    down_path = str(PROJECT_ROOT / "BOT_WORK" / "Downloads")
class MockTRANSFER:
    successful_downloads = []
class MockTaskError:
    failed_links = []
class MockMSG:
    status_msg = None

class MockMessages:
    download_name = ""
    status_head = ""

variables_mock.BOT = MockBOT
variables_mock.Messages = MockMessages
variables_mock.Paths = MockPaths
variables_mock.TRANSFER = MockTRANSFER
variables_mock.TaskError = MockTaskError
variables_mock.MSG = MockMSG

sys.modules["colab_leecher.utility.variables"] = variables_mock

helper_mock = types.ModuleType("colab_leecher.utility.helper")
helper_mock.keyboard = lambda: None
helper_mock.sysINFO = lambda: ""
sys.modules["colab_leecher.utility.helper"] = helper_mock

message_safety_mock = types.ModuleType("colab_leecher.utility.message_safety")
message_safety_mock.escape_html = lambda x: x
sys.modules["colab_leecher.utility.message_safety"] = message_safety_mock

# 2. Block colab_leecher parent package executions (prevents pyrogram import)
colab_leecher_mock = types.ModuleType("colab_leecher")
sys.modules["colab_leecher"] = colab_leecher_mock

downlader_mock = types.ModuleType("colab_leecher.downlader")
sys.modules["colab_leecher.downlader"] = downlader_mock

# Load session JSON string to mock credentials loading
test_settings = PROJECT_ROOT / "test" / "instagrapi_settings_test.json"
if test_settings.exists():
    MockSetting.instagram_session = test_settings.read_text(encoding="utf-8")
    print("[+] Loaded mock instagram_session from test_settings.")

# Delete existing settings files to enforce recreating from credentials mock
repo_settings = PROJECT_ROOT / "instagrapi_settings.json"
work_settings = Path(MockPaths.WORK_PATH) / "instagrapi_settings.json"
for f in (repo_settings, work_settings):
    if f.exists():
        try:
            f.unlink()
            print(f"[+] Deleted {f.name} to test self-healing path.")
        except Exception:
            pass

# Initialize Paths
os.makedirs(MockPaths.WORK_PATH, exist_ok=True)
os.makedirs(MockPaths.down_path, exist_ok=True)

# Mock status MSG object
class MockStatusMsg:
    async def edit_text(self, text, reply_markup=None):
        print(f"[Render Update] {text.splitlines()[0] if text else ''}")
        return self

MockMSG.status_msg = MockStatusMsg()

# 3. Load the module under test directly using importlib
grapi_path = PROJECT_ROOT / "colab_leecher" / "downlader" / "instagram_grapi.py"
spec = importlib.util.spec_from_file_location("colab_leecher.downlader.instagram_grapi", str(grapi_path))
instagram_grapi = importlib.util.module_from_spec(spec)
instagram_grapi.__package__ = "colab_leecher.downlader"
sys.modules["colab_leecher.downlader.instagram_grapi"] = instagram_grapi

# Execute module
spec.loader.exec_module(instagram_grapi)

async def test():
    url = "https://www.instagram.com/p/DZzndRyD82d/utm_source=ig_web_copy_link"
    print(f"[*] Testing grapi_post_download with URL: {url}")
    
    success = await instagram_grapi.grapi_post_download(url, 1)
    print(f"\n[*] Result: {success}")
    print(f"[*] Successful downloads list: {MockTRANSFER.successful_downloads}")

if __name__ == "__main__":
    asyncio.run(test())
