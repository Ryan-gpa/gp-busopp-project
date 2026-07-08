with open('webapp/api/main.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

spa_start_idx = -1
status_start_idx = -1

for i, line in enumerate(lines):
    if line.startswith("_FRONTEND_DIR ="):
        spa_start_idx = i - 4  # Includes the comments above it
    elif line.startswith("@app.get(\"/api/admin/system-status\")"):
        status_start_idx = i

if spa_start_idx != -1 and status_start_idx != -1 and status_start_idx > spa_start_idx:
    spa_block = lines[spa_start_idx:status_start_idx]
    status_block = lines[status_start_idx:]
    
    new_lines = lines[:spa_start_idx] + status_block + ["\n"] + spa_block
    
    with open('webapp/api/main.py', 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
    print('Fixed ordering!')
else:
    print('Not found or already ordered', spa_start_idx, status_start_idx)
