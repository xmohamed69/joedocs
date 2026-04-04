import os
 
header = """# Copyright (c) 2025 JoeLinkAI / JoeCorp. All rights reserved.
# Unauthorized copying, distribution, or modification is strictly prohibited.
# See LICENSE for details.
 
"""
 
count = 0
for root, dirs, files in os.walk('.'):
    dirs[:] = [d for d in dirs if d not in ['venv312', '__pycache__', '.git', 'migrations']]
    for f in files:
        if f.endswith('.py'):
            path = os.path.join(root, f)
            try:
                content = open(path, encoding='utf-8', errors='ignore').read()
                if 'Copyright' not in content:
                    open(path, 'w', encoding='utf-8').write(header + content)
                    count += 1
                    print(f'  + {path}')
            except Exception as e:
                print(f'  SKIP {path}: {e}')
 
print(f'\nDone — {count} files updated.')