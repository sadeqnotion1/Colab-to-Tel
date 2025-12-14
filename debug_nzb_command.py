"""
Debug NZB command in Colab
Run this cell to check if NZB handler is working
"""

import sys
import logging

# Check if bot is running
print("="*70)
print("🔍 NZB Command Diagnostic")
print("="*70)

# 1. Check if bot module is loaded
try:
    sys.path.insert(0, '/content/Telegram-Leecher')
    from colab_leecher import colab_bot
    from colab_leecher.utility.variables import BOT
    print("\n✅ Bot module loaded successfully")
except Exception as e:
    print(f"\n❌ Failed to load bot module: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

# 2. Check NZB settings
print("\n📋 NZB Configuration:")
print(f"   Providers: {list(BOT.Setting.nzb_providers.keys()) if BOT.Setting.nzb_providers else 'None'}")
print(f"   Active Provider: {BOT.Setting.nzb_active_provider or 'None'}")

if BOT.Setting.nzb_active_provider and BOT.Setting.nzb_providers:
    provider_config = BOT.Setting.nzb_providers.get(BOT.Setting.nzb_active_provider, {})
    print(f"   Host: {provider_config.get('host', 'N/A')}")
    print(f"   Port: {provider_config.get('port', 'N/A')}")
    print(f"   SSL: {provider_config.get('ssl', 'N/A')}")
    print(f"   Connections: {provider_config.get('connections', 'N/A')}")
else:
    print("   ⚠️ No provider configured!")

# 3. Check if NZB state variable exists
print(f"\n🔧 NZB State:")
print(f"   nzb_waiting: {getattr(BOT.State, 'nzb_waiting', 'ATTRIBUTE NOT FOUND!')}")

# 4. Check if handlers are registered
print(f"\n📡 Registered Handlers:")
if colab_bot:
    handler_count = len(colab_bot.dispatcher.groups.get(0, []))
    print(f"   Total handlers: {handler_count}")

    # Try to find NZB handler
    nzb_handler_found = False
    for handler in colab_bot.dispatcher.groups.get(0, []):
        if hasattr(handler, 'callback'):
            func_name = handler.callback.__name__
            if 'nzb' in func_name.lower():
                print(f"   ✅ Found NZB handler: {func_name}")
                nzb_handler_found = True

    if not nzb_handler_found:
        print(f"   ⚠️ No NZB-related handler found!")
else:
    print("   ❌ Bot instance not found!")

# 5. Test NZB file import
print(f"\n📦 NZB Module Import Test:")
try:
    from colab_leecher.downlader.nzb import NZBDownloader
    print(f"   ✅ NZBDownloader imported successfully")
except Exception as e:
    print(f"   ❌ Failed to import NZBDownloader: {e}")
    import traceback
    traceback.print_exc()

# 6. Enable debug logging
print(f"\n🐛 Enabling DEBUG logging...")
logging.basicConfig(level=logging.DEBUG, force=True)
print(f"   ✅ Debug logging enabled")

print("\n" + "="*70)
print("📝 Next Steps:")
print("   1. Send /nzb to your bot")
print("   2. Watch the cell where bot is running for log output")
print("   3. Look for lines like: 'Received /nzb from...'")
print("="*70)
