import sys

with open('webapp/api/main.py', 'r', encoding='utf-8') as f:
    content = f.read()

spa_idx = content.find('Serve built Vite frontend')
status_idx = content.find('@app.get("/api/admin/system-status")')

if spa_idx != -1 and status_idx != -1 and status_idx > spa_idx:
    # Need to go back to the start of the comment block for SPA
    block_start = content.rfind('\n', 0, spa_idx)
    block_start = content.rfind('#', 0, block_start)
    
    spa_block = content[block_start:status_idx]
    status_block = content[status_idx:]
    
    new_content = content[:block_start] + status_block + '\n\n' + spa_block
    with open('webapp/api/main.py', 'w', encoding='utf-8') as f:
        f.write(new_content)
    print('Fixed ordering!')
else:
    print('Not found or already ordered', spa_idx, status_idx)
