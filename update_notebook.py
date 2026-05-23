import json
import os

notebook_path = r'notebooks\COtoTEL_v3_00_02_U1.ipynb'

with open(notebook_path, 'r', encoding='utf-8') as f:
    nb = json.load(f)

# Update the setup cell
for cell in nb['cells']:
    if cell['cell_type'] == 'code' and 'COMPLETE COLAB SETUP' in ''.join(cell['source']):
        source = cell['source']
        new_source = []
        for line in source:
            # Fix apt-get
            if 'apt-get update -qq && apt-get install -y -qq ffmpeg aria2 megatools' in line:
                line = line.replace('apt-get update -qq && apt-get install -y -qq ffmpeg aria2 megatools', 
                                    'add-apt-repository -y universe && apt-get update -qq && apt-get install -y -qq ffmpeg aria2 megatools')
            
            # Fix pip install issues (the old logic with critical_packages)
            # Actually, I'll just replace the whole pip block with a simpler one
            if 'log.info("Installing Python dependencies...")' in line:
                # We can keep it simple now that requirements.txt is fixed
                pass
            
            # Ensure git pull is clean
            if 'cmd_pull = f"git pull origin {branch_name}"' in line:
                line = line.replace('cmd_pull = f"git pull origin {branch_name}"', 
                                    'cmd_pull = f"git fetch origin {branch_name} && git reset --hard origin/{branch_name}"')
            
            new_source.append(line)
        cell['source'] = new_source

# Save the updated notebook
with open(notebook_path, 'w', encoding='utf-8') as f:
    json.dump(nb, f, indent=1)

print("Successfully updated notebook.")
