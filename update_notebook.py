import json
import os

notebook_path = r'notebooks\COtoTEL_v3_00_02_U1.ipynb'

if not os.path.exists(notebook_path):
    print(f"ERROR: Notebook not found at {notebook_path}")
    exit(1)

with open(notebook_path, 'r', encoding='utf-8') as f:
    nb = json.load(f)

updated = False
# Update the setup cell
for cell in nb['cells']:
    if cell['cell_type'] == 'code' and 'COMPLETE COLAB SETUP' in ''.join(cell['source']):
        print("Found COMPLETE COLAB SETUP cell. Processing...")
        # Join characters/lines into a single string to bypass character-splitting issues
        source_str = ''.join(cell['source'])
        
        # 1. Fix apt-get and add universe repo
        old_apt = 'apt-get update -qq && apt-get install -y -qq ffmpeg aria2 megatools'
        new_apt = 'add-apt-repository -y universe && apt-get update -qq && apt-get install -y -qq ffmpeg aria2 megatools'
        if old_apt in source_str:
            source_str = source_str.replace(old_apt, new_apt)
            print("- Applied add-apt-repository -y universe fix")
        else:
            print("- add-apt-repository -y universe fix not applied (already updated or pattern mismatch)")
        
        # 2. Fix git pull to be robust (fetch & reset --hard)
        old_git = 'cmd_pull = f"git pull origin {branch_name}"'
        new_git = 'cmd_pull = f"git fetch origin {branch_name} && git reset --hard origin/{branch_name}"'
        if old_git in source_str:
            source_str = source_str.replace(old_git, new_git)
            
            # Also replace the print/warning statement for git pull
            source_str = source_str.replace(
                'log.warning(f"Git pull issues:\\n{proc_pull.stderr}")',
                'log.warning(f"Git fetch/reset issues:\\n{proc_pull.stderr}")'
            )
            print("- Applied git pull fetch/reset fix")
        else:
            print("- git pull fetch/reset fix not applied (already updated or pattern mismatch)")
        
        # Split back into normal clean list of lines (keeping the \n at ends)
        cell['source'] = source_str.splitlines(keepends=True)
        updated = True
        break

if updated:
    # Save the updated notebook
    with open(notebook_path, 'w', encoding='utf-8') as f:
        json.dump(nb, f, indent=1)
    print("Successfully updated notebook and formatted it into a clean list of lines!")
else:
    print("ERROR: Setup cell with 'COMPLETE COLAB SETUP' not found in notebook.")
