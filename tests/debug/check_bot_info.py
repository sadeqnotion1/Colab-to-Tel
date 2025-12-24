"""Check which bot this token belongs to"""
import json
import requests

# Load credentials
with open('credentials.json', 'r') as f:
    creds = json.load(f)

bot_token = creds['BOT_TOKEN']

# Get bot info
response = requests.get(f'https://api.telegram.org/bot{bot_token}/getMe')
data = response.json()

if data['ok']:
    bot_info = data['result']
    print("="*70)
    print("BOT INFORMATION:")
    print("="*70)
    print(f"Bot ID: {bot_info['id']}")
    print(f"Bot Username: @{bot_info['username']}")
    print(f"Bot Name: {bot_info['first_name']}")
    print(f"Can Join Groups: {bot_info.get('can_join_groups', 'N/A')}")
    print(f"Can Read All Group Messages: {bot_info.get('can_read_all_group_messages', 'N/A')}")
    print("="*70)
    print(f"\nMake sure you're messaging: @{bot_info['username']}")
    print(f"In a PRIVATE chat (not a group)")
    print("="*70)
else:
    print(f"Error: {data}")
